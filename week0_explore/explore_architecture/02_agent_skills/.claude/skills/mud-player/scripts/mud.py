#!/usr/bin/env python3
"""
mud.py — persistent connection manager for playing a MUD over a raw TCP socket.

Why a daemon? A MUD is a single stateful session: you log in once, then every
command depends on that same connection. Discrete agent tool calls each run in a
fresh process, so they can't hold a socket open between calls. This script keeps
one background "daemon" process alive that owns the socket; the foreground
subcommands (send/read/status/stop) talk to it through a named pipe and a log
file. That mirrors what `nc localhost 4000` does interactively, but survives
across many separate invocations.

Subcommands:
  start            Open the connection and auto-log-in (idempotent).
  send "<cmd>"     Send one MUD command, print what the game replies.
  read [n]         Print the last n lines of session output (default 40).
  status           Report whether the connection is alive.
  stop             Log out cleanly and shut the daemon down.
  raw "<text>"     Send text with NO trailing newline (rare; for menu prompts).

Everything is plain sockets — no telnet, no external deps beyond Python 3.
"""

import os
import re
import sys
import time
import select
import socket
import signal
import tempfile
import subprocess

# ---- Connection + credential defaults (override via environment) ------------
HOST = os.environ.get("MUD_HOST", "localhost")
PORT = int(os.environ.get("MUD_PORT", "4000"))
USER = os.environ.get("MUD_USER", "dummy")
PASSWORD = os.environ.get("MUD_PASSWORD", "helloworld")

# Runtime files live outside the skill dir so we never commit session state.
SESSION_DIR = os.environ.get(
    "MUD_SESSION_DIR", os.path.join(tempfile.gettempdir(), "mud-session")
)
FIFO = os.path.join(SESSION_DIR, "in")          # commands: foreground -> daemon
LOG = os.path.join(SESSION_DIR, "session.log")  # cleaned, human-readable output
PIDFILE = os.path.join(SESSION_DIR, "daemon.pid")

# How long `send` waits for the game to finish replying. The game streams a
# reply then goes quiet; we return once output has been idle for SETTLE seconds
# (or MAX_WAIT elapses). This "wait until quiet" beats a fixed sleep because MUD
# reply latency varies a lot between a quick `look` and a room full of mobs.
SETTLE = float(os.environ.get("MUD_SETTLE", "0.6"))
MAX_WAIT = float(os.environ.get("MUD_MAX_WAIT", "8"))


# ---- Byte cleaning -----------------------------------------------------------
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")   # CSI colour/cursor codes
_OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")  # OSC title strings
_OTHER_ESC = re.compile(r"\x1b[@-Z\\-_]")          # stray single-char escapes


def strip_telnet(data: bytes) -> bytes:
    """Remove telnet IAC negotiation sequences (0xFF ...).

    CircleMUD/tbaMUD negotiates client options with IAC (byte 0xFF) sequences.
    We don't need to answer them — the game proceeds regardless — but the raw
    bytes are garbage if shown to a human, so we drop them here.
    """
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b == 0xFF:  # IAC
            if i + 1 < n and data[i + 1] == 0xFF:  # IAC IAC = literal 0xFF
                out.append(0xFF)
                i += 2
                continue
            if i + 1 < n and data[i + 1] == 0xFA:  # SB ... subnegotiation
                j = i + 2
                while j + 1 < n and not (data[j] == 0xFF and data[j + 1] == 0xF0):
                    j += 1
                i = j + 2  # skip through IAC SE
                continue
            i += 3  # WILL/WONT/DO/DONT + option byte
            continue
        out.append(b)
        i += 1
    return bytes(out)


def clean(data: bytes) -> str:
    """Turn raw socket bytes into readable text (strip telnet + ANSI + junk)."""
    text = strip_telnet(data).decode("utf-8", "ignore")
    text = _ANSI.sub("", text)
    text = _OSC.sub("", text)
    text = _OTHER_ESC.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "")
    # Drop remaining control chars except newline and tab.
    return "".join(ch for ch in text if ch >= " " or ch in "\n\t")


# ---- Small process/file helpers ---------------------------------------------
def daemon_pid():
    """Return the live daemon PID, or None if not running."""
    try:
        with open(PIDFILE) as f:
            pid = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None
    try:
        os.kill(pid, 0)  # signal 0 = existence check
    except OSError:
        return None
    return pid


def log_size():
    try:
        return os.path.getsize(LOG)
    except OSError:
        return 0


def read_since(offset):
    """Read cleaned log text written after byte `offset`."""
    try:
        with open(LOG, "r", errors="ignore") as f:
            f.seek(offset)
            return f.read()
    except OSError:
        return ""


# ============================================================================
# Daemon: owns the socket. Runs in the background, reopened as `mud.py _daemon`.
# ============================================================================
def run_daemon():
    os.makedirs(SESSION_DIR, exist_ok=True)
    # Truncate log for a fresh session.
    open(LOG, "w").close()

    sock = socket.create_connection((HOST, PORT), timeout=30)
    sock.setblocking(False)

    logf = open(LOG, "ab", buffering=0)

    def pump_socket():
        """Drain any pending socket bytes into the cleaned log. Returns text."""
        chunks = []
        while True:
            try:
                data = sock.recv(4096)
            except BlockingIOError:
                break
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
        if chunks:
            text = clean(b"".join(chunks))
            logf.write(text.encode("utf-8"))
            return text
        return ""

    def wait_for(pattern, timeout=15):
        """Accumulate output until `pattern` (regex, case-insensitive) appears."""
        deadline = time.time() + timeout
        buf = ""
        rx = re.compile(pattern, re.IGNORECASE)
        while time.time() < deadline:
            buf += pump_socket()
            if rx.search(buf):
                return buf
            time.sleep(0.15)
        return buf

    def send_line(text):
        sock.sendall((text + "\r\n").encode("utf-8"))

    # ---- Auto-login by walking each prompt (never blind-sleeping) -----------
    # The client-detection handshake takes a few seconds; sending the name too
    # early gets it eaten, so we wait for the "name" prompt before anything.
    # tbaMUD's post-password path is: PRESS RETURN gate -> account menu ->
    # "1" to enter the game -> the in-game status prompt (e.g. "24H 100M 69V >").
    # The in-game prompt is what we key on to know we're actually playing.
    PROMPT = r"\d+H\s+\d+M\s+\d+V"  # in-game status prompt

    wait_for(r"by what name|wish to be known", timeout=25)
    send_line(USER)
    wait_for(r"password", timeout=15)
    send_line(PASSWORD)

    # Advance through whatever gates appear until we reach the in-game prompt.
    # Each gate is answered with the appropriate keypress: a bare return for the
    # PRESS RETURN pause, "1" for the account menu. We cap the attempts so a bad
    # password (which loops back to a name/password prompt) can't spin forever.
    for _ in range(8):
        state = wait_for(PROMPT + r"|press return|make your choice|enter the game"
                         r"|by what name|incorrect", timeout=12)
        if re.search(PROMPT, state):
            break  # we're in the game
        if re.search(r"by what name|incorrect|password:", state, re.IGNORECASE):
            logf.write(b"\n[mud.py] Login failed (bad credentials?). Stop and retry.\n")
            break
        if re.search(r"make your choice|enter the game", state, re.IGNORECASE):
            send_line("1")
        else:  # PRESS RETURN (or an unknown pause) -> nudge with a blank line
            send_line("")
    pump_socket()

    # ---- Serve commands from the FIFO --------------------------------------
    # Watch the socket AND the command pipe together with select(), so the
    # socket is drained continuously — even while no command is pending. If we
    # blocked on reading the pipe instead, a command's reply would sit unread in
    # the socket buffer until the NEXT command woke us, shifting every reply one
    # call late (and missing async output like combat rounds entirely).
    #
    # Open the pipe O_RDWR|O_NONBLOCK: O_RDWR keeps a writer permanently attached
    # so we never see EOF when a `send` process closes its end, and NONBLOCK lets
    # select drive the timing. We reassemble whole command lines ourselves since
    # a nonblocking read can return partial data.
    fifo_fd = os.open(FIFO, os.O_RDWR | os.O_NONBLOCK)

    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__("flag", True))

    def handle(line):
        line = line.rstrip("\n")
        if line == "__STOP__":
            stop["flag"] = True
        elif line.startswith("__RAW__"):
            sock.sendall(line[len("__RAW__"):].encode("utf-8"))
        else:
            send_line(line)

    cmdbuf = ""
    while not stop["flag"]:
        rlist, _, _ = select.select([sock, fifo_fd], [], [], 0.2)
        if sock in rlist:
            pump_socket()
        if fifo_fd in rlist:
            try:
                chunk = os.read(fifo_fd, 4096).decode("utf-8", "ignore")
            except BlockingIOError:
                chunk = ""
            cmdbuf += chunk
            while "\n" in cmdbuf:
                line, cmdbuf = cmdbuf.split("\n", 1)
                handle(line)
                pump_socket()

    try:
        send_line("quit")
        time.sleep(0.4)
        pump_socket()
    except OSError:
        pass
    sock.close()
    logf.close()


# ============================================================================
# Foreground subcommands
# ============================================================================
def ensure_session_dir():
    os.makedirs(SESSION_DIR, exist_ok=True)
    if not os.path.exists(FIFO):
        os.mkfifo(FIFO)


def cmd_start():
    if daemon_pid():
        print("Already connected. Use `send`, `read`, or `stop`.")
        return 0
    ensure_session_dir()
    # Launch this same file as a detached daemon.
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "_daemon"],
        stdout=open(os.path.join(SESSION_DIR, "daemon.out"), "ab"),
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    with open(PIDFILE, "w") as f:
        f.write(str(proc.pid))

    # Wait for login to settle. The in-game status prompt (e.g. "24H 100M 69V >")
    # or a login-failure note is our signal that startup is done.
    deadline = time.time() + 30
    while time.time() < deadline:
        text = read_since(0)
        if re.search(r"\d+H\s+\d+M\s+\d+V|Login failed", text):
            break
        if daemon_pid() is None:
            print("Daemon exited during startup. Check", os.path.join(SESSION_DIR, "daemon.out"))
            return 1
        time.sleep(0.5)
    print(read_since(0).strip()[-2000:])
    print("\n[connected — send commands with: mud send \"look\"]")
    return 0


def cmd_send(args, raw=False):
    if daemon_pid() is None:
        print("Not connected. Run `mud start` first.")
        return 1
    payload = " ".join(args)
    offset = log_size()
    with open(FIFO, "w") as f:
        f.write(("__RAW__" + payload if raw else payload) + "\n")

    # Wait for THIS command's reply. Every in-game reply ends with the status
    # prompt (e.g. "24H 100M 74V >"), so a fresh prompt appearing after our
    # command is the reliable "reply complete" signal — far better than a bare
    # idle timeout, which returns early and shifts each reply onto the next call
    # when the server is slow. Any prompt in text written after `offset` belongs
    # to this command (the previous prompt is before `offset`).
    # Fallbacks: if no prompt shows (menus/sub-prompts don't emit one), fall
    # back to idle-settle so we still return; MAX_WAIT caps the whole wait.
    prompt_rx = re.compile(r"\d+H\s+\d+M\s+\d+V")
    start = time.time()
    last_size = offset
    last_change = time.time()
    while time.time() - start < MAX_WAIT:
        time.sleep(0.15)
        size = log_size()
        if size != last_size:
            last_size = size
            last_change = time.time()
        idle = time.time() - last_change
        new = read_since(offset)
        if prompt_rx.search(new) and idle >= 0.25:
            break  # full reply captured, ending on a prompt
        if idle >= SETTLE and size > offset:
            break  # sub-prompt / no-prompt reply that has gone quiet
    out = read_since(offset).strip()
    print(out if out else "[no response — the game may be waiting on a prompt]")
    return 0


def cmd_read(args):
    n = int(args[0]) if args else 40
    try:
        with open(LOG, "r", errors="ignore") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        print("No session log yet. Run `mud start`.")
        return 1
    print("\n".join(lines[-n:]))
    return 0


def cmd_status():
    pid = daemon_pid()
    if pid:
        print(f"Connected (daemon pid {pid}). Session dir: {SESSION_DIR}")
        return 0
    print("Not connected.")
    return 1


def cmd_stop():
    pid = daemon_pid()
    if pid is None:
        print("Not connected.")
        return 0
    try:
        with open(FIFO, "w") as f:
            f.write("__STOP__\n")
    except OSError:
        pass
    for _ in range(20):
        if daemon_pid() is None:
            break
        time.sleep(0.2)
    if daemon_pid():
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        os.remove(PIDFILE)
    except OSError:
        pass
    print("Disconnected.")
    return 0


USAGE = __doc__


def main(argv):
    if not argv:
        print(USAGE)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "_daemon":
        run_daemon()
        return 0
    if cmd == "start":
        return cmd_start()
    if cmd == "send":
        return cmd_send(rest)
    if cmd == "raw":
        return cmd_send(rest, raw=True)
    if cmd == "read":
        return cmd_read(rest)
    if cmd == "status":
        return cmd_status()
    if cmd == "stop":
        return cmd_stop()
    print(USAGE)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
