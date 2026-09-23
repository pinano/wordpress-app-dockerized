# Capacity and Sizing Guide

Proper sizing is crucial for running stable WordPress applications, especially when hosting multiple tenants on the same server. This guide covers how to size your deployments safely.

## Automated Sizing Profiles
The provided `Makefile` includes predefined sizing profiles that automatically adjust `.env` variables to apply balanced CPU, Memory, caching, and database limits based on the expected application size.

To apply a profile, run:
```bash
make size-small   # For low traffic (< 500 visits/day)
make size-medium  # For medium traffic (500 - 5000 visits/day)
make size-large   # For high traffic (> 5000 visits/day)
```

Always run `make start` or `make restart` to apply environment variable changes to running containers.
You can view active sizing values easily using `make size-show`.

### Profile Reference Matrix

| Profile | Target Traffic | App CPU / RAM | PHP OPcache | FPM Children / Apache Workers | DB CPU / RAM | DB Buffer Pool | DB Max Conn |
|---|---|---|---|---|---|---|---|
| **SMALL** | < 500 visits/day | 0.5 / 256M | 64 MB | 5 | 1.0 / 512M | 128M | 50 |
| **MEDIUM** | 500 - 5,000 visits/day | 1.0 / 512M | 128 MB | 10 | 2.0 / 1.0G | 256M | 100 |
| **LARGE** | > 5,000 visits/day | 2.0 / 1.0G | 192 MB | 20 | 4.0 / 2.0G | 512M | 300 |

### Anti-OOM Memory Sizing Rule

Inside the `app` container, memory is shared between:
1. **PHP OPcache** (fixed shared memory allocation).
2. **PHP-FPM Worker Pool** (~30-35 MB per active WordPress worker).
3. **Apache Web Server** (~50-80 MB baseline).

To prevent the Linux kernel from triggering **OOM Killer** (`SIGKILL` on workers, dropped MariaDB sockets, and Traefik 404s), every profile strictly guarantees:
$$\text{OPcache} + (\text{Workers} \times 35\text{ MB}) + \text{Apache} < \text{APP\_MEMORY}$$

Any traffic spikes exceeding the active worker count safely queue in Apache/FPM (`listen.backlog`) with sub-second delay instead of crashing the container.

## Critical Warning: SWAP Usage and tmpfs

> [!CAUTION]
> **Active SWAP memory on the host completely destroys WordPress performance when using `tmpfs`.**

This stack intentionally mounts the temporary `/var/www/html/tmp` directory into a fast, in-memory `tmpfs` volume instead of the persistent disk. This is because PHP/WordPress heavily depend on the `/tmp` directory for session storage and various temporary caches.

Using `tmpfs` is dramatically faster than SSD I/O. However, if your host server runs out of physical RAM and begins using SWAP files:
1. Docker will seamlessly begin swapping the `tmpfs` volume back to the slow, physical disk.
2. Because the OS kernel manages SWAP, it abstracts the disk latency from Docker. 
3. The "in-memory" cache operations effectively become heavily delayed disk operations, causing catastrophic performance collapses and 500/504 Gateway errors.

**Recommendation:**
- Strictly control memory using `size-small` on hosts with low RAM.
- Use monitoring tools (like Netdata, Datadog or Prometheus) to specifically alert if the host begins allocating SWAP.
- Ensure the sum of all `*_MEMORY` limits across all tenants combined never exceeds 90% of the host's physical RAM, leaving 10% for OS overhead.
