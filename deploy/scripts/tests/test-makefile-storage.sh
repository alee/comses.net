#!/usr/bin/env bash
# Build must leave private deployed storage alone while retaining local setup.
set -euo pipefail

REPO_ROOT=$(CDPATH= cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/comses-make-storage.XXXXXX")
trap 'rm -rf "$FIXTURE"' EXIT

cp "$REPO_ROOT/Makefile" "$FIXTURE/Makefile"
touch "$FIXTURE"/{config.mk,.env,base.yml,dev.yml,staging.yml,test.yml,prod.yml}
mkdir -p "$FIXTURE/docker/secrets"
touch "$FIXTURE/docker/secrets"/{db_password,.pgpass,django_secret_key}
touch "$FIXTURE/.env"

for environment in staging prod dev; do
    output=$(make -n -C "$FIXTURE" build \
        "DEPLOY_ENVIRONMENT=$environment" \
        "COMSES_APP_ROOT=$FIXTURE" \
        "COMSES_SHARED_ROOT=$FIXTURE/docker/shared" \
        "COMSES_POSTGRES_ROOT=$FIXTURE/docker/pgdata" \
        "COMSES_SECRETS_ROOT=$FIXTURE/docker/secrets")
    if [[ "$environment" == dev ]]; then
        [[ "$output" == *"chmod 0777"* ]] || {
            echo "development build no longer prepares local Elasticsearch directories" >&2
            exit 1
        }
    else
        [[ "$output" != *"chmod 0777"* ]] || {
            echo "$environment build would make Elasticsearch directories world-writable" >&2
            exit 1
        }
    fi
done

echo "Build storage prerequisites are environment-specific."
