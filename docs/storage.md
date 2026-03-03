# Storage Architecture

Understanding how this stack handles storage is critical for data integrity, performance tuning, and backup strategies.

## Tmpfs vs Persistent Storage

The stack utilizes two distinctly different storage mechanisms:

### 1. Ephemeral Storage (`tmpfs`)
* **Location:** `/var/www/html/tmp` on both `app` and `cron` containers.
* **Behavior:** Volatile. Data is stored directly in the host's RAM memory up to the limit defined in your `.env` profile.
* **Pros:** Extremely fast read/write operations (ideal for Zend Framework's `file` cache backend or native PHP sessions).
* **Cons:** **All data is permanently lost when the container is restarted or stopped.**

> [!WARNING]
> If your ZF1 application relies on storing user session files or temporary PDF generations on disk, be aware that a `make restart` will instantly log out all currently active users. If you need session persistence across deployments, consider enabling the [Redis Session Backend](redis.md) instead.

### 2. Persistent Storage (Volumes)
* **Location:** `./mariadb_data` (Database) and `./docroot` (Application Code & Uploads).
* **Behavior:** Data is persistently mapped to folders on your host machine.
* **Pros:** Data survives container rebuilds, restarts, and system reboots.
* **Cons:** Slower I/O compared to RAM.

Always ensure that any user-uploaded content (images, documents) is saved outside of the `tmp` directory, directly into your `public` or a dedicated `data` folder within `docroot`.
