# Application Environment (APP_ENV)

The Docker stack includes an `APP_ENV` variable in the `.env` file that controls the behavior of both the underlying web server (PHP-FPM/Apache) and your legacy Zend Framework 1.x application.

---

## 1. How the Server Reacts

The `serversideup/php` image natively listens to `APP_ENV`:

### `APP_ENV=production` (Default)
- **Error Hiding:** PHP fatal errors, warnings, and stack traces are suppressed from the user's browser (Display Errors Off) and routed to the hidden internal logs. This protects your infrastructure from information leaks.
- **Aggressive Caching:** OPcache strict protections and performance optimizations are fully enabled, assuming the source code is immutable.

### `APP_ENV=development`
- **Error Display:** Code failures instantly render detailed errors with file paths and line numbers directly in the browser (Display Errors On).
- **Relaxed Environment:** Disables strict OPcache protections, forcing PHP to recompile changed files on every request. This lets you live-edit code and see results without restarting the container.

---

## 2. Integrating with Legacy ZF1 Code

Zend Framework 1.x is old enough that it does **not** automatically read this variable. Legacy ZF1 applications usually look for a specific constant (e.g., `APPLICATION_ENV`) defined in `public/index.php`.

To ensure your framework runs in the exact same mode as the Docker container (and accurately switches database configs or enables onscreen `Zend_Log`), you should update your application's entry point.

### Updating `public/index.php`

Look for the traditional `APPLICATION_ENV` definition:

```php
// Old legacy definition:
define('APPLICATION_ENV', (getenv('APPLICATION_ENV') ? getenv('APPLICATION_ENV') : 'production'));
```

Change it to read the modern Docker variable `APP_ENV`:

```php
// Modernized definition reading from the Docker container:
define('APPLICATION_ENV', (getenv('APP_ENV') ? getenv('APP_ENV') : 'production'));
```

By making this small change, your container's `APP_ENV` variable (defined in `.env`) will act as the single source of truth, synchronizing the server's error reporting with Zend Framework's internal environment!

---

## 3. OPcache Settings for Development

When switching to `APP_ENV=development`, you should also adjust the OPcache settings in your `.env` file to allow live code editing without container restarts:

```ini
APP_ENV=development
PHP_OPCACHE_VALIDATE_TIMESTAMPS=1
PHP_OPCACHE_REVALIDATE_FREQ=0
PHP_EXTENSION_XDEBUG=1
```

This makes PHP recheck files on every request, so code changes are visible instantly. **Remember to revert these settings in production** (the `.env.dist` defaults are already optimized for production).
