# Logging Guide

There are two types of logs to monitor in this stack:

| Type | Command |
|---|---|
| Docker container logs (Apache, PHP errors, `error_log()`) | `make logs app` |
| WordPress debug log (`debug.log` to file) | `make logs wordpress` |

```bash
make logs             # follow all container logs (all services)
make logs app         # follow only the app container
make logs wordpress   # tail the WordPress debug.log inside the container
```

## What appears automatically

| Source | Visible in `make logs app`? | Visible in `make logs wordpress`? |
|---|---|---|
| Apache access log (every request + status code) | ✅ Yes | ❌ No |
| PHP fatal / parse errors | ✅ Yes | ❌ No |
| `error_log()` calls in PHP code | ✅ Yes | ❌ No |
| WordPress `WP_DEBUG_LOG` writes | ❌ No | ✅ Yes |

## PHP error display in development

In `APP_ENV=development`, `display_errors` is **Off** by default — errors are written
to the log instead of being printed in the HTTP response. This prevents stack traces
from leaking while still capturing all errors via `error_log()` / WP Debug Logger.

To enable WordPress debugging, add the following to `wp-config.php`:

```php
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', '/var/www/html/wp-content/debug.log');
define('WP_DEBUG_DISPLAY', false); // Keep false to hide errors from users
```

> ⚠️ Never enable `WP_DEBUG_DISPLAY` in production — it exposes stack traces to end users.

## WordPress application log (`debug.log`)

The WordPress application log is written to:

```
/var/www/html/wp-content/debug.log   (inside the container)
```

To tail it in real time:

```bash
make logs wordpress
```
