# Advanced Deployments with Docker Compose Override

The default `docker-compose.yml` provided in this project is explicitly tuned for single-host deployments (LXC containers, Virtual Machines, or bare-metal servers). 

However, if you intend to scale this stack across multiple nodes, integrate it with existing infrastructure, or deploy via Kubernetes (using Kompose) or Docker Swarm, you should never edit `docker-compose.yml` directly. Instead, use a `docker-compose.override.yml` file.

Docker Compose automatically applies any configuration found in `docker-compose.override.yml` on top of your base `docker-compose.yml`.

## Use Cases for Override

### 1. Scaling to Multiple Nodes (Docker Swarm)

If you are deploying 30+ instances across a swarm cluster, the default `bridge` networks and volume mounts will not suffice. You will need to override networks to use `overlay` and volumes to use networked storage (like NFS or GlusterFS).

```yaml
# docker-compose.override.yml
services:
  app:
    deploy:
      replicas: 3 # Scale to 3 containers
      placement:
        constraints:
          - node.role == worker
    volumes:
      - /mnt/nfs/projecta/docroot:/var/www/html # Override local bind mount with NFS

networks:
  backnet:
    driver: overlay # Change network driver for multi-node communication
```

### 2. Custom Environment Variable Injections

You can use the override file to define custom secrets or environments that you do not want to manage in the `.env` file (for example, CI/CD pipeline injections).

```yaml
# docker-compose.override.yml
services:
  app:
    environment:
      CI_PIPELINE_ID: "12345"
      MAINTENANCE_MODE: "true"
```

### 3. Exposing Ports Externally

By default, the MariaDB and SFTP ports are bound strictly to `127.0.0.1` for security in multi-tenant shared hosts. If you have an external management tool that needs direct access, override the port binding.

```yaml
# docker-compose.override.yml
services:
  db:
    ports:
      # Expose externally, but map to the specific port defined in .env
      - "0.0.0.0:${DB_HOST_PORT}:3306" 
```

## Note on Kubernetes
If you plan to migrate this stack to Kubernetes, use [Kompose](https://kompose.io/) to translate your `docker-compose.yml` into native K8s manifests. Kompose will respect override files during translation.
