# Deployed storage layout and migration

This runbook is the canonical host-path contract for staging and production.
Development keeps repository-local defaults.

## Path classification

| Class | Host path | Container path / consumer | Owner and mode |
|---|---|---|---|
| 1. Source-controlled, replaceable | `/srv/apps/comses` excluding `docker/`, `.env`, and generated `docker-compose.yml` | build contexts and read-only configuration binds | deployment user; normal checkout modes |
| 2. Durable application state | `/srv/apps/comses/docker/shared/{library,media,repository,data,incoming,.latest}` | `/shared/*`; selected paths are read-only in nginx | `0:0`; directories `0755` |
| 2. PostgreSQL state | `/srv/apps/comses/docker/pgdata` | db `/var/lib/postgresql/data`; not mounted by server | `999:999`; `0700` |
| 6. Disposable cache or generated state | `/srv/apps/comses/docker/shared/{redis,elasticsearch,static,vite,statistics,tests,extract,uploads}` | Redis, Elasticsearch, collected assets, exports, tests, and temporary upload/restore data | Redis `999:1000` `0750`; Elasticsearch `1000:0` `0750`; remaining directories `0:0` `0755` |
| 2. ACME challenge state | `/srv/apps/comses/docker/shared/tls/well-known` | nginx `/srv/.well-known` | `0:0`; `0755` |
| 3. Durable logs | `/srv/logs/comses` and `/srv/logs/comses/nginx` | server/db `/shared/logs`; nginx `/var/log/nginx` | root `0755`; nginx `101:101` `0750` |
| 4. Backup data | `/srv/apps/comses/docker/shared/backups` (Borg `repo`, imports, DB dumps, and preserved clusters) | `/shared/backups`; Borg uses `/shared/backups/repo` | deployment UID/GID (default `1000:1000`); `0750` |
| 5. Secret material | `/srv/apps/comses/docker/secrets` and `/srv/apps/comses/.env` | Compose secrets and runtime environment | deployment user; directory `0700`, files `0600` |
| 6. Disposable state | Compose `sockets` volume, container writable layers, and Docker-managed service stdout | Unix sockets and runtime scratch data | service-specific; no authoritative data |

The application-local Borg repository remains `/shared/backups/repo` inside the
server container. Infrastructure replicates it to
`borg-replica@backup-01.staging.internal:/`. Keep its SSH private key and pinned
host key under `/srv/apps/comses/docker/secrets`; never put replication
credentials in the shared tree, log tree, image, or repository. TLS terminates
upstream in the current production topology. If certificate private keys are
later stored on this host, place them under the secret root, not
`docker/shared/tls` (which contains only public ACME challenge files).
Application and nginx file logs are bound to `/srv/logs/comses`; PostgreSQL,
Redis, and Elasticsearch currently emit operational diagnostics to container
stdout. Those streams are disposable. If infrastructure retains them, its
Docker logging driver/data root must also use Cinder-backed storage or remote
log transport rather than the host root filesystem.

The UID/GID values match the currently pinned images and are parameters to
`deploy/scripts/prepare-host-storage`. Confirm them after an image change with
`docker run --rm --entrypoint id <image>` before changing infrastructure.

## Infrastructure preparation

The checkout must already exist at the physical path `/srv/apps/comses`; it
must not be a symlink. Verify that `/srv/apps/comses` and `/srv/logs/comses`
resolve to Cinder-backed filesystems rather than `/`, then run:

```bash
cd /srv/apps/comses
sudo deploy/scripts/prepare-host-storage
deploy/scripts/storage-preflight
```

The preparation script is idempotent. It creates and repairs only the exact
writable directories listed above. It does not recursively traverse the
checkout or a durable tree and rejects a symlink at any managed root.

For staging and production, `config.mk` must resolve these values:

```make
COMSES_APP_ROOT=/srv/apps/comses
COMSES_SHARED_ROOT=/srv/apps/comses/docker/shared
COMSES_POSTGRES_ROOT=/srv/apps/comses/docker/pgdata
COMSES_LOG_ROOT=/srv/logs/comses
COMSES_SECRETS_ROOT=/srv/apps/comses/docker/secrets
```

## In-place migration from the previous layout

Staging and production already use `/srv/apps/comses`. Do not move or copy the
checkout and do not copy the entire `docker/shared` tree: library files, media,
the repository, Redis state, and the Borg repository are already in their final
locations. PostgreSQL remains isolated at `docker/pgdata`; only logs, secrets,
and the nginx ACME challenge path change host locations. Run this procedure
independently on each host, staging first.

These steps copy rather than move data. The old paths and Elasticsearch named
volumes remain available for rollback. Run each block separately and stop when
a check fails.

1. Preflight the mount, space, sources, symlinks, Compose project, and running
   containers:

   ```bash
   cd /srv/apps/comses
   test "$(pwd -P)" = /srv/apps/comses
   sudo findmnt -T /srv/apps/comses
   sudo findmnt -T /srv
   df -h /srv/apps/comses /srv
   test -f docker/pgdata/PG_VERSION
   test -d docker/shared/logs
   test -f build/secrets/db_password
   sudo find -P docker/pgdata docker/shared/logs build/secrets -type l -print
   docker compose ps
   docker compose -f docker-compose.yml config > build/secrets/compose-before-srv-migration.yml
   chmod 0600 build/secrets/compose-before-srv-migration.yml
   docker volume ls
   ```

   Investigate every listed symlink before continuing; the copy commands must
   not follow it. Record the current Compose project name from `docker compose
   ls` for rollback. Confirm that the saved Compose render contains the current
   `docker/pgdata`, `docker/shared/logs`, `build/secrets`, and Elasticsearch
   named-volume sources before proceeding.

   If `docker/shared/postgres` contains a PostgreSQL cluster, stop and follow
   `docs/agents/postgresql-upgrade-runbook.md` to return it to isolated storage.
   If both secret directories contain different files, stop and identify the
   authoritative copy. The deployment preflight refuses ambiguous secret paths
   until the operator records `COMSES_STORAGE_AUTHORITY=new` after verification.

2. Stop services without deleting their containers, networks, or named
   volumes, then create the new empty destinations:

   ```bash
   docker compose stop
   sudo deploy/scripts/prepare-host-storage
   ```

3. Copy only the paths that change. `-x` stays on the source filesystem and
   `--safe-links` does not follow unsafe operator-created links:

   ```bash
   sudo rsync -aHAXx --numeric-ids --safe-links docker/shared/logs/ /srv/logs/comses/
   sudo rsync -aHAXx --numeric-ids --safe-links build/secrets/ docker/secrets/
   sudo rsync -aHAXx --numeric-ids --safe-links deploy/nginx/well-known/ docker/shared/tls/well-known/
   ```

   The final command copies only existing public ACME challenge material. The
   source-controlled nginx configuration remains in `deploy/nginx`.
   Elasticsearch indexes are deliberately not copied from the old named
   volumes. They are rebuildable class-6 state, and `make deploy` runs
   `inv prepare` to rebuild the index in the new bind mounts.

4. Verify without changing either copy, then repair only the exact managed
   directory owners and modes:

   ```bash
   sudo rsync -aHAXxcni --delete --numeric-ids --safe-links docker/shared/logs/ /srv/logs/comses/
   sudo rsync -aHAXxcni --delete --numeric-ids --safe-links build/secrets/ docker/secrets/
   sudo rsync -aHAXxcni --delete --numeric-ids --safe-links deploy/nginx/well-known/ docker/shared/tls/well-known/
   sudo env COMSES_STORAGE_AUTHORITY=new deploy/scripts/prepare-host-storage
   cmp build/secrets/db_password docker/secrets/db_password
   ```

   The dry runs should emit no differences. Do not recursively `chown` any
   copied tree.

5. Explicitly select the verified destinations, render Compose, recreate the
   services, and validate the mounts and application:

   ```bash
   grep -qxF 'COMSES_STORAGE_AUTHORITY=new' config.mk || printf '\nCOMSES_STORAGE_AUTHORITY=new\n' >> config.mk
   make docker-compose.yml
   make verify-compose-storage
   docker compose up -d --force-recreate
   make verify-container-storage
   docker compose exec -T db pg_isready -U comsesnet -d comsesnet
   docker compose exec -T server ./manage.py check
   ```

   Inspect `docker compose config` and `docker inspect` for every service. All
   durable bind sources must begin with `/srv/apps/comses/docker/shared`,
   `/srv/apps/comses/docker/pgdata`, or `/srv/logs/comses`; source-controlled
   binds must begin with `/srv/apps/comses`.

## Rollback

Do not reverse-copy a database that the new stack has modified. Stop the new
containers and recreate the old configuration using the saved render and the
Compose project name recorded during preflight:

```bash
cd /srv/apps/comses
docker compose stop
docker compose --project-name <recorded-project-name> --project-directory /srv/apps/comses -f docker/secrets/compose-before-srv-migration.yml up -d --force-recreate
```

This remounts the untouched `docker/pgdata`, `docker/shared/logs`, legacy
secrets, and Elasticsearch named volumes. Retain those sources until staging or
production has passed its acceptance and backup-retention period. None of the
migration scripts deletes them automatically.

## Operations after migration

Run deploy, upgrade, maintenance, and rollback commands from
`/srv/apps/comses`. Use `docker compose stop` for brief filesystem maintenance;
reserve `docker compose down` for operations that actually require container or
network removal. Never use recursive `chown` on `/srv/apps/comses`,
`docker/shared`, or `/srv/logs/comses`.
