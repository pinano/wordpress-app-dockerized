# Application Environment (APP_ENV)

The Docker stack includes an `APP_ENV` variable in the `.env` file that controls the behavior of both the underlying web server (PHP-FPM/Apache) and your WordPress application.

---

## 1. How the Server Reacts

The `serversideup/php` image natively listens to `APP_ENV`:

### `APP_ENV=production`
- **Error Hiding:** PHP fatal errors, warnings, and stack traces are suppressed from the user's browser (Display Errors Off) and routed to the hidden internal logs. This protects your infrastructure from information leaks.
- **Aggressive Caching:** OPcache strict protections and performance optimizations are fully enabled, assuming the source code is immutable.

### `APP_ENV=development` (Default in `.env.dist`)
- **Error Display:** Code failures instantly render detailed errors with file paths and line numbers directly in the browser (Display Errors On).
- **Relaxed Environment:** Disables strict OPcache protections, forcing PHP to recompile changed files on every request. This lets you live-edit code and see results without restarting the container.

---

## 2. Integrating with WordPress

WordPress natively supports environment types via `WP_ENVIRONMENT_TYPE`.
To ensure your WordPress site runs in the exact same mode as the Docker container, you can update your `wp-config.php`.

### Updating `wp-config.php`

Add the following to read the modern Docker variable `APP_ENV`:

```php
define('WP_ENVIRONMENT_TYPE', getenv('APP_ENV') ?: 'production');
```

By making this small change, your container's `APP_ENV` variable (defined in `.env`) will act as the single source of truth, synchronizing the server's error reporting with WordPress's internal environment!

---

## 3. OPcache Settings for Development

When `APP_ENV=development`, the stack automatically configures OPcache to revalidate files on every request (via `docker/scripts/set-env-vars.sh`). You don't need to manually set these values unless you want to override them.

If you want to explicitly force specific OPcache settings, you can add them to your `.env` file:

```ini
PHP_OPCACHE_VALIDATE_TIMESTAMPS=1
PHP_OPCACHE_REVALIDATE_FREQ=0
PHP_EXTENSION_XDEBUG=1
```

This makes PHP recheck files on every request, so code changes are visible instantly. **Remember to switch `APP_ENV=production` for production deployments** (which will automatically disable timestamp validation).
