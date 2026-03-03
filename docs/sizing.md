# Capacity and Sizing Guide

Proper sizing is crucial for running stable Zend Framework 1.x legacy applications, especially when hosting multiple tenants on the same server. This guide covers how to size your deployments safely.

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

## Critical Warning: SWAP Usage and tmpfs

> [!CAUTION]
> **Active SWAP memory on the host completely destroys Zend Framework performance when using `tmpfs`.**

This stack intentionally mounts the temporary `/var/www/html/tmp` directory into a fast, in-memory `tmpfs` volume instead of the persistent disk. This is because ZF1 heavily depends on the `/tmp` directory for session storage and various framework caches (core, classes, pages, forms).

Using `tmpfs` is dramatically faster than SSD I/O. However, if your host server runs out of physical RAM and begins using SWAP files:
1. Docker will seamlessly begin swapping the `tmpfs` volume back to the slow, physical disk.
2. Because the OS kernel manages SWAP, it abstracts the disk latency from Docker. 
3. The "in-memory" cache operations effectively become heavily delayed disk operations, causing catastrophic performance collapses and 500/504 Gateway errors.

**Recommendation:**
- Strictly control memory using `size-small` on hosts with low RAM.
- Use monitoring tools (like Netdata, Datadog or Prometheus) to specifically alert if the host begins allocating SWAP.
- Ensure the sum of all `*_MEMORY` limits across all tenants combined never exceeds 90% of the host's physical RAM, leaving 10% for OS overhead.
