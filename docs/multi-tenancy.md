# Multi-Tenancy on Single Host

This stack is designed to be easily replicable, allowing you to host dozens of WordPress applications on a single server without port collisions or dependency hell.

## Scenario: Running 30+ WordPress Apps

Running multiple applications on the same server requires careful resource management and a centralized router (reverse proxy) to direct traffic based on domains rather than ports.

### Step 1: Central Proxy (Traefik)
Do not expose the `8080` port directly to the host for every project. Instead, keep all traffic inside Docker networks.
This stack comes pre-configured for **Traefik**, a modern reverse proxy that automatically discovers Docker containers.
By relying on the labels provided in `docker-compose.yml`, Traefik will route `yourdomain.com` directly to the correct container.

### Step 2: Use Isolated Docker Networks
Each project establishes its own `backnet` (e.g., `projecta_backnet`, `projectb_backnet`). This ensures that:
- Project A cannot access Project B's database.
- Database credentials can be identical across projects without risk of cross-contamination if networks are isolated.

### Step 3: Resource Allocation
When running multiple applications, it's critical to prevent a single buggy application from consuming all the server's CPU or RAM.
Always use the predefined sizing profiles when setting up a new tenant:
- Run `make size-small` for low-traffic sites to cap memory and CPU usage aggressively.
- Run `make size-show` periodically to audit custom allocations.

### Step 4: Network and Routing Limitations (Scaling beyond 30+ Apps)
While Docker can easily run hundreds of containers, you may encounter network bottlenecks around the 30-40 application mark:
1. **DNS Resolution**: Docker's internal DNS resolver can become overwhelmed if 40 applications simultaneously re-resolve hostnames.
2. **Bridge Overhead**: Docker's bridge networks use `iptables` rules. Managing hundreds of isolated `backnet` bridges adds CPU overhead to the host network stack.
3. **Traefik Load**: Traefik acts as the central router and SSL terminator. For extremely high densities, consider allocating dedicated CPU/Memory limits to the Traefik container itself to prevent it from becoming a bottleneck.

If you reach these limits, it is usually time to transition from a single-host deployment to a multi-node Swarm or Kubernetes cluster (see `docs/docker-compose-override-examples.md`).

### Step 5: Avoid Port Collisions
By default, the `docker-compose.yml` only exposes the MariaDB port directly to the `127.0.0.1` host interface for debugging purposes.
The port is calculated automatically using `PROJECT_ID` (e.g., MariaDB maps to `33${PROJECT_ID}`).
If you are running multiple projects, you **must** assign a unique `PROJECT_ID` in each project's `.env` file to ensure ports don't collide.
* Example Project A: `PROJECT_ID=001` → MariaDB on port `33001`
* Example Project B: `PROJECT_ID=002` → MariaDB on port `33002`
