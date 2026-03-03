# Redis Integration with Zend Framework 1.x (Powered by Valkey)

The current Docker stack includes an optional Redis-compatible service (powered by `valkey/valkey:7.2-alpine`) prepared for high-traffic environments. Valkey is a drop-in replacement for Redis that runs entirely in RAM, offering sub-millisecond response times, which is ideal for storing caches and user sessions, relieving the load on MariaDB and the hard drive. All interactions with this container use the standard Redis nomenclature and protocols.

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

## 2. Configuration in the Legacy Application (ZF1)

Zend Framework 1.x has the `Zend_Cache` component which can be adapted to use Redis. There are two main use cases: Application Cache and Session Handling.

### Use Case A: Application Cache (Zend_Cache)

To use Redis as a caching backend, a widely used community library called `Cm_Cache_Backend_Redis` is commonly used (very popular in Magento 1 and ZF1 ecosystems). Since Valkey is fully compatible with the Redis protocol, this works seamlessly.

In your `application/configs/application.ini` file, the configuration to hook this backend would be as follows:

```ini
; Basic frontend configuration
resources.cachemanager.general.frontend.name                            = Core
resources.cachemanager.general.frontend.options.lifetime                = 7200
resources.cachemanager.general.frontend.options.automatic_serialization = true

; Redis backend configuration
resources.cachemanager.general.backend.name                             = "Cm_Cache_Backend_Redis"

; IMPORTANT: The server must point to the service name in the docker-compose (redis)
resources.cachemanager.general.backend.options.server                   = "redis" 
resources.cachemanager.general.backend.options.port                     = "6379"
```

**Usage example in a Controller/Model:**
```php
$cache = clone $this->getInvokeArg('bootstrap')->getResource('cachemanager')->getCache('general');

$cacheKey = 'popular_articles_list';

if (!$result = $cache->load($cacheKey)) {
    // If not in cache, perform the heavy DB query
    $result = $model->performHeavyQuery();
    
    // Save in Redis for next time
    $cache->save($result, $cacheKey);
}

return $result;
```

### Use Case B: Session Storage (Recommended)

Even if you don't want to refactor code to implement data caching, **moving user sessions to Redis** offers a massive performance improvement without needing to touch PHP code.

By moving sessions to Redis, heavy read/write operations on disk files (`/tmp/sessions`) are avoided, taking advantage of the volatile cache in RAM.

Add these directives to your `application.ini` (or uncomment them if they previously existed pointing to disk):

```ini
; Disable potential session saving in the database if you had it
; resources.session.saveHandler.class = "Zend_Session_SaveHandler_DbTable"

; Configure PHP to use the native Redis extension for sessions
phpSettings.session.save_handler = "redis"
phpSettings.session.save_path    = "tcp://redis:6379"

; Optional: Configure cookie/session lifetime
phpSettings.session.cookie_lifetime = 86400
phpSettings.session.gc_maxlifetime  = 86400
```

With this simple configuration change, user logins and navigation will be processed instantly through the in-memory Redis service.

