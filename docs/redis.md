# Redis Integration with WordPress (Powered by Valkey)

The current Docker stack includes an optional Redis-compatible service (powered by `valkey/valkey:7.2-alpine`) prepared for high-traffic environments. Valkey is a drop-in replacement for Redis that runs entirely in RAM, offering sub-millisecond response times, which is ideal for storing object cache and user sessions, relieving the load on MariaDB and the hard drive. All interactions with this container use the standard Redis nomenclature and protocols.

---

## 1. Enabling the Redis Container

By default, the Redis container **is not initialized** to save resources in small projects. To enable it in your project, you must use Docker Profiles.

1. Open your `.env` file.
2. Find the `COMPOSE_PROFILES` variable and set it to `redis`:
   ```bash
   COMPOSE_PROFILES=redis
   ```
3. Restart the stack:
   ```bash
   make restart
   ```

This will spin up a new container named `[PROJECT_NAME]-redis` that will only be accessible from within the internal Docker network (`backnet`) at host `redis` and port `6379`.

---

## 2. Configuration in WordPress

WordPress can leverage Redis for object caching and session storage to greatly improve performance.

### Use Case A: Object Cache (Redis Object Cache Plugin)

To use Redis as a caching backend, you should use a plugin such as "Redis Object Cache" or "WP Redis". 

You must define the connection parameters in your `wp-config.php`:

```php
// IMPORTANT: The server must point to the service name in the docker-compose (redis)
define('WP_REDIS_HOST', 'redis');
define('WP_REDIS_PORT', 6379);
// Optional variables:
// define('WP_REDIS_DATABASE', 0);
// define('WP_REDIS_PASSWORD', 'your-password');
```

Once the plugin is installed and activated, it will intercept database queries and cache the results in Redis.

### Use Case B: Session Storage (Recommended)

Even if you use a different caching mechanism, moving user sessions to Redis offers a direct performance improvement without needing to touch application logic.

Add these directives to your custom `docker/php/custom.ini` file if you want PHP to handle sessions through Redis:

```ini
; Configure PHP to use the native Redis extension for sessions
session.save_handler = redis
session.save_path    = "tcp://redis:6379"

; Optional: Configure cookie/session lifetime
session.cookie_lifetime = 86400
session.gc_maxlifetime  = 86400
```

With this simple configuration change, user data stored in $_SESSION will be processed instantly through the in-memory Redis service.
