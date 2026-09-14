import os
from unittest import TestCase
from unittest.mock import patch

from invoke import Context

from curator.invoke_tasks.database import dump_migration, restore_from_dump


class MigrationDumpTaskTests(TestCase):
    @patch("curator.invoke_tasks.database.os.replace")
    @patch("curator.invoke_tasks.database.create_pgpass_file")
    @patch("curator.invoke_tasks.database.get_database_settings")
    @patch("curator.invoke_tasks.database.pathlib.Path.mkdir")
    def test_dump_migration_uses_timestamped_artifact_path(
        self, mkdir, get_database_settings, create_pgpass_file, replace
    ):
        get_database_settings.return_value = {
            "db_name": "comsesnet",
            "db_host": "db",
            "db_user": "comsesnet",
            "db_password": "secret",
        }
        ctx = Context()

        with patch.dict(
            os.environ, {"DB_MIGRATION_TIMESTAMP": "20260523T220000"}, clear=False
        ), patch.object(ctx, "run") as run_mock:
            dump_migration(ctx, force=True)

        create_pgpass_file.assert_called_once_with(ctx, db_key="default")
        mkdir.assert_called_once_with(parents=True, exist_ok=True)
        run_mock.assert_called_once()
        replace.assert_called_once()
        self.assertIn(
            "/migration-artifacts/20260523T220000/comsesnet.dump.tmp",
            run_mock.call_args.args[0],
        )


class MigrationRestoreTaskTests(TestCase):
    @patch("curator.invoke_tasks.database.drop")
    @patch("curator.invoke_tasks.database.get_database_settings")
    @patch("curator.invoke_tasks.database.pathlib.Path.is_file", return_value=True)
    def test_restore_from_dump_prefers_migration_artifact_when_timestamp_is_set(
        self, is_file, get_database_settings, drop
    ):
        get_database_settings.return_value = {
            "db_name": "comsesnet",
            "db_host": "db",
            "db_user": "comsesnet",
            "db_password": "secret",
        }
        ctx = Context()

        with patch.dict(
            os.environ, {"DB_MIGRATION_TIMESTAMP": "20260523T220000"}, clear=False
        ), patch.object(ctx, "run") as run_mock:
            restore_from_dump(ctx, force=True, migrate=False)

        drop.assert_called_once_with(ctx, database="default", create=True)
        run_mock.assert_called_once()
        self.assertIn(
            "/migration-artifacts/20260523T220000/comsesnet.dump",
            run_mock.call_args.args[0],
        )
        self.assertIn("pg_restore", run_mock.call_args.args[0])
