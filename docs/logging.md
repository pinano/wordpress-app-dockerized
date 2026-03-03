# Logging Guide

There are three sources of logs to monitor in this stack:

| Type | Command |
|---|---|
| Docker container logs (Apache, PHP errors, `error_log()`) | `make logs app` |
| WordPress debug log (`WP_DEBUG_LOG`) | `make logs wordpress` |
| All container logs combined | `make logs` |

```bash
make logs             # follow all container logs (all services)
make logs app         # follow only the app container
make logs wordpress   # tail the WordPress debug.log inside the container
```

## What appears automatically

| Source | Visible in `make logs app`? | Visible in `make logs wordpress`? |
|---|---|---|
| Apache access log (every request + status code) | ✅ Yes | ❌ No |
| PHP fatal / parse errors | ✅ Yes (via error forwarder) | ❌ No |
| `error_log()` calls in PHP code | ✅ Yes (via error forwarder) | ❌ No |
| WordPress `WP_DEBUG_LOG` writes | ❌ No | ✅ Yes |

> ℹ️ PHP errors are routed to Docker logs via a `tail` forwarder process started by `init-app.sh`.
> The actual error log file lives at `/var/www/html/tmp/php_errors.log` (tmpfs, ephemeral).

## PHP error display in development

In `APP_ENV=development`, `display_errors` is **Off** by default — errors are written
to the log instead of being printed in the HTTP response. This prevents stack traces
from leaking while still capturing all errors via `error_log()` / WP Debug Logger.

To enable WordPress debugging, add the following to `wp-config.php`:

```php
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true); // Logs to wp-content/debug.log by default
define('WP_DEBUG_DISPLAY', false); // Keep false to hide errors from users
```

> ⚠️ Never enable `WP_DEBUG_DISPLAY` in production — it exposes stack traces to end users.

## WordPress application log (`debug.log`)

The WordPress application log is written to:

```
/var/www/html/public/wp-content/debug.log   (inside the container)
```

To tail it in real time:

```bash
make logs wordpress
```
