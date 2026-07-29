# Step 02: The Registry – Issues Fixed

## Wrapper Script Syntax Error

**Issue:** The bash wrapper script at `bin/ruby/02_the_registry` had two problems:
1. Unclosed double quote on line 3
2. Path used hyphen (`02_the-registry`) instead of underscore (`02_the_registry`)

**Error:**
```
./bin/ruby/02_the_registry: line 3: unexpected EOF while looking for matching `"'
./bin/ruby/02_the_registry: line 5: syntax error: unexpected end of file
```

**Fix:** Corrected the path and closed the quote:
```bash
cd "$(dirname "$0")/../../ruby/02_the_registry"
bundle exec ruby examples/example.rb
```

## Ruby Settings Handling

**Issue:** The `fetch` method in `lib/boukensha/tasks/base.rb` didn't handle `nil` settings gracefully, causing a NoMethodError when trying to index into nil.

**Error:**
```
undefined method '[]' for nil (NoMethodError)
```

**Root cause:** When `config.tasks(:player)` returns `nil` (because no `settings.yaml` exists), that nil was passed directly to `fetch()` which tried to call `[]` on it.

**Fix:** Added a guard clause to `fetch()` to return nil early if settings isn't a Hash:
```ruby
def fetch(settings, key)
  return nil unless settings.is_a?(Hash)
  settings[key.to_s] || settings[key.to_sym]
end
```

## Result

Script now runs successfully. All tool registration and dispatching works as expected:
- Registry accepts tool definitions
- Tools can be dispatched by name with parameters
- Unknown tool error is properly caught and reported
