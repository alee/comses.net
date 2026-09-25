import csv
import fcntl
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.core.management.base import CommandError
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
    def test_download_rows_use_stable_user_tokens_without_ip_addresses(self):
        class Downloads:
            def select_related(self, *args):
                return self

            def order_by(self, *args):
                return self

            def iterator(self):
                for user_id in (42, 42, 43, None):
                    yield SimpleNamespace(
                        date_created="2026-09-24",
                        release=SimpleNamespace(get_absolute_url=lambda: "/release/1"),
                        ip_address="192.0.2.1",
                        user_id=user_id,
                        reason="research",
                        affiliation="University",
                        industry="academia",
                        referrer="example.org",
                    )

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "downloads.csv"
            with override_settings(DOWNLOAD_ANALYTICS_HMAC_KEY="11" * 32):
                Command().export_all_downloads(Downloads(), destination)
            with destination.open(newline="") as stream:
                reader = csv.DictReader(stream)
                fieldnames = reader.fieldnames
                rows = list(reader)

            with override_settings(DOWNLOAD_ANALYTICS_HMAC_KEY="22" * 32):
                Command().export_all_downloads(Downloads(), destination)
            with destination.open(newline="") as stream:
                rotated_rows = list(csv.DictReader(stream))

        self.assertIn("user_token", fieldnames)
        self.assertNotIn("user_id", fieldnames)
        self.assertNotIn("ip_address", fieldnames)
        self.assertEqual(rows[0]["user_token"], rows[1]["user_token"])
        self.assertNotEqual(rows[0]["user_token"], rows[2]["user_token"])
        self.assertEqual(len(rows[0]["user_token"]), 64)
        self.assertEqual(rows[3]["user_token"], "")
        self.assertNotEqual(rows[0]["user_token"], rotated_rows[0]["user_token"])
        self.assertEqual(rows[0]["reason"], "research")
        self.assertEqual(rows[0]["affiliation"], "University")
        self.assertEqual(rows[0]["referrer"], "example.org")

    def test_export_refuses_missing_key_before_writing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "downloads.csv"
            with override_settings(DOWNLOAD_ANALYTICS_HMAC_KEY=None):
                with self.assertRaisesRegex(CommandError, "DOWNLOAD_ANALYTICS_HMAC_KEY"):
                    Command().export_all_downloads(None, destination)
            self.assertFalse(destination.exists())
