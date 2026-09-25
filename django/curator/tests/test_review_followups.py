import csv
import fcntl
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.test import override_settings
from invoke import Context

from curator.invoke_tasks.borg import restore, restore_database, restore_files
from curator.management.commands.curator_statistics import Command


class RestoreLockTests(TestCase):
    def test_restore_variants_reject_concurrent_backup_operation(self):
        with tempfile.TemporaryDirectory() as share_dir:
            backup_root = Path(share_dir) / "backups"
            backup_root.mkdir()
            lock_path = backup_root / ".backup.lock"
            with (
                lock_path.open("w") as lockfile,
                override_settings(BACKUP_ROOT=backup_root, SHARE_DIR=share_dir),
                patch("curator.invoke_tasks.borg.confirm"),
                patch("curator.invoke_tasks.borg.check_archive") as check_archive,
            ):
                fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
                commands = (
                    lambda: restore(Context(), repo="repo", archive="archive", force=True),
                    lambda: restore_files(Context(), repo="repo", archive="archive"),
                    lambda: restore_database(Context(), repo="repo", archive="archive"),
                )
                for command in commands:
                    with self.assertRaisesRegex(RuntimeError, "cannot start restore"):
                        command()
            check_archive.assert_not_called()


class DownloadExportTests(TestCase):
    def test_download_rows_export_user_pk_without_username(self):
        class Downloads:
            def select_related(self, *args):
                return self

            def order_by(self, *args):
                return self

            def iterator(self):
                yield SimpleNamespace(
                    date_created="2026-09-24",
                    release=SimpleNamespace(get_absolute_url=lambda: "/release/1"),
                    ip_address="192.0.2.1",
                    user_id=42,
                    reason="research",
                    affiliation="University",
                    industry="academia",
                    referrer="example.org",
                )

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "downloads.csv"
            Command().export_all_downloads(Downloads(), destination)
            with destination.open(newline="") as stream:
                rows = list(csv.DictReader(stream))

        self.assertEqual(rows[0]["user_id"], "42")
        self.assertNotIn("user", rows[0])
