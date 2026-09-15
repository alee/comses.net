# PostgreSQL Data Moves and Upgrades

This runbook covers two distinct operations:

1. Recovering a cluster from the briefly used `docker/shared/postgres` layout
   back to isolated `docker/pgdata` storage without changing versions.
2. Upgrading PostgreSQL with a logical `pg_dump` and `pg_restore` migration.

Never use a filesystem move to upgrade PostgreSQL across major versions.

## Recover from the exposed shared layout

A direct move is appropriate only when all of these are true:

- PostgreSQL will use the same image and major version after the move.
- `docker/shared/postgres` is the only directory containing authoritative data.
- `docker/pgdata` is absent or empty.
- The database and application services are stopped.
- Both paths are on the same filesystem.

Inspect both locations before changing anything:

```bash
docker compose stop server db
sudo find docker/pgdata docker/shared/postgres -mindepth 1 -maxdepth 1 -print
sudo cat docker/shared/postgres/PG_VERSION
sudo stat -c '%d %n' docker/shared/postgres docker
```

If both directories contain data, stop. Identify the authoritative cluster by
checking its PostgreSQL version, timestamps, and application contents. Do not
merge PostgreSQL data directories.

When `docker/pgdata` exists but is empty, remove only that empty directory and
move the shared cluster into isolated storage:

```bash
sudo rmdir docker/pgdata
sudo mv docker/shared/postgres docker/pgdata
sudo chown 999:999 docker/pgdata
sudo chmod 0700 docker/pgdata
docker compose up -d db server
docker compose exec db pg_isready -U "${DB_USER}" -d "${DB_NAME}"
docker compose exec server ./manage.py check
```

The move preserves ownership within the cluster; only the bind mount's top-level
directory is normalized. It is atomic when both paths report the same filesystem
device ID. Keep a logical database backup before starting even when the move is
atomic.

After validating the isolated cluster, set this in `config.mk` if a retained
copy under `docker/shared/postgres` would otherwise trigger the storage guard:

```make
COMSES_POSTGRES_AUTHORITY=isolated
```

## Major-version upgrade

PostgreSQL data directories are major-version-specific. Use the repository's
`borg.backup-all` and `db.restore-from-dump` tasks for a logical migration. There
is currently no one-command Make target for this operation.

### 1. Record versions and create a backup

```bash
export DB_MIGRATION_TIMESTAMP=20260914T190000
export DB_NAME=comsesnet
export DB_USER=comsesnet
docker compose exec db psql -U "${DB_USER}" -d "${DB_NAME}" -c 'SELECT version();'
docker compose exec db psql -U "${DB_USER}" -d "${DB_NAME}" -c 'SELECT PostGIS_Full_Version();'
docker compose exec server inv borg.backup-all
docker compose exec \
  -e DB_MIGRATION_TIMESTAMP="${DB_MIGRATION_TIMESTAMP}" \
  -e DB_NAME="${DB_NAME}" server sh -c \
  'mkdir -p "/shared/backups/db-migration-artifacts/$DB_MIGRATION_TIMESTAMP" && cp "/shared/backups/latest/$DB_NAME.dump" "/shared/backups/db-migration-artifacts/$DB_MIGRATION_TIMESTAMP/$DB_NAME.dump"'
```

Confirm the copied custom-format dump is readable:

```bash
docker compose exec server pg_restore --list \
  "/shared/backups/db-migration-artifacts/${DB_MIGRATION_TIMESTAMP}/${DB_NAME}.dump" >/dev/null
```

### 2. Preserve the source cluster

Stop writers before moving the source data directory:

```bash
docker compose stop server db
export PGDATA_ROOT=/srv/apps/comses/docker/pgdata
export PGDATA_BACKUP_ROOT=/srv/apps/comses/docker/shared/backups/postgres-clusters
sudo install -d -o 999 -g 999 -m 0700 \
  "${PGDATA_BACKUP_ROOT}/${DB_MIGRATION_TIMESTAMP}"
sudo mv "${PGDATA_ROOT}" \
  "${PGDATA_BACKUP_ROOT}/${DB_MIGRATION_TIMESTAMP}/postgres"
sudo install -d -o 999 -g 999 -m 0700 "${PGDATA_ROOT}"
```

Do not delete the preserved cluster until the migration has passed validation
and the backup-retention period.

### 3. Select and start the target version

Update the `db.image` value in `base.yml` to the intended PostGIS/PostgreSQL
image. PostgreSQL 18 images may require the bind target `/var/lib/postgresql`
instead of `/var/lib/postgresql/data`; follow the selected image's documented
mount contract.

Update `postgresql-client-<major>` and the `/usr/lib/postgresql/<major>/bin`
path in `django/Dockerfile` and `deploy/conf/.env.template` to the target major,
then rebuild the server image. The dump must be created with the source-major
client before this change; restore and subsequent backups use the target-major
client.

Then regenerate Compose and start the empty target cluster:

```bash
make docker-compose.yml
docker compose build server
docker compose up -d db
docker compose exec db pg_isready -U "${DB_USER}" -d "${DB_NAME}"
docker compose up -d server
```

### 4. Restore and migrate

```bash
docker compose exec server inv db.restore-from-dump \
  --dumpfile="/shared/backups/db-migration-artifacts/${DB_MIGRATION_TIMESTAMP}/${DB_NAME}.dump" \
  --force --no-migrate
docker compose exec server ./manage.py migrate --noinput
```

### 5. Validate

```bash
docker compose exec db psql -U "${DB_USER}" -d "${DB_NAME}" -c 'SELECT version();'
docker compose exec db psql -U "${DB_USER}" -d "${DB_NAME}" -c 'SELECT PostGIS_Full_Version();'
docker compose exec server ./manage.py check
docker compose exec server ./manage.py migrate --plan
docker compose exec server pg_restore --list \
  "/shared/backups/db-migration-artifacts/${DB_MIGRATION_TIMESTAMP}/${DB_NAME}.dump" >/dev/null
```

Run the repository test and application smoke-test procedures before accepting
the new cluster.

## Rollback

Do not copy a modified target cluster back over the source. Stop services,
preserve the failed target separately, restore the original image and mount
configuration, and move the untouched source cluster back:

```bash
docker compose stop server db
sudo mv "${PGDATA_ROOT}" \
  "${PGDATA_BACKUP_ROOT}/${DB_MIGRATION_TIMESTAMP}/failed-target"
sudo mv "${PGDATA_BACKUP_ROOT}/${DB_MIGRATION_TIMESTAMP}/postgres" \
  "${PGDATA_ROOT}"
make docker-compose.yml
docker compose up -d db server
```

Verify the original database and application before removing any migration
artifact.
