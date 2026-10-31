"""Contract tests for Makefile deployment and shutdown commands."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
FAKE_DOCKER = ROOT / "deploy/tests/fixtures/fake_docker.py"
FAKE_NOOP = ROOT / "deploy/tests/fixtures/fake_noop.py"
FAKE_PREFLIGHT = ROOT / "deploy/tests/fixtures/fake_storage_preflight.py"


class MakefileContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="comses-make-contract-"
        )
        self.root = Path(self.temporary_directory.name)
        self.project = self.root / "physical checkout"
        self.alias = self.root / "logical-checkout"
        self.secrets = self.root / "secrets"
        self.shared = self.root / "shared"
        self.project.mkdir()
        self.secrets.mkdir()
        self.shared.mkdir()
        self.alias.symlink_to(self.project, target_is_directory=True)

        shutil.copy(ROOT / "Makefile", self.project / "Makefile")
        for name in (
            "config.mk",
            "base.yml",
            "dev.yml",
            "staging.yml",
            "test.yml",
            "prod.yml",
            "docker-compose.yml",
        ):
            (self.project / name).touch()
        (self.project / ".env").write_text(
            "RELEASE_VERSION=fixture\n", encoding="utf-8"
        )
        for name in (
            "db_password",
            ".pgpass",
            "django_secret_key",
            "download_analytics_hmac_key",
        ):
            (self.secrets / name).touch()

        scripts = self.project / "deploy/scripts"
        scripts.mkdir(parents=True)
        shutil.copy(FAKE_PREFLIGHT, scripts / "storage-preflight")
        shutil.copy(FAKE_NOOP, scripts / "envreplace")
        (scripts / "storage-preflight").chmod(0o755)
        (scripts / "envreplace").chmod(0o755)

        self.log = self.root / "docker.jsonl"
        self.ps_count = self.root / "docker-ps-count"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def make_arguments(self, target, deployment, entry=None):
        return [
            "make",
            "--no-print-directory",
            "-C",
            str(entry or self.project),
            target,
            f"DEPLOY_ENVIRONMENT={deployment}",
            f"COMSES_APP_ROOT={self.project}",
            f"COMSES_SHARED_ROOT={self.shared}",
            f"COMSES_POSTGRES_ROOT={self.root / 'pgdata'}",
            f"COMSES_LOG_ROOT={self.root / 'logs'}",
            f"COMSES_BACKUPS_ROOT={self.root / 'backups'}",
            f"COMSES_SECRETS_ROOT={self.secrets}",
            f"DOCKER=python3 {FAKE_DOCKER}",
            "SLEEP=true",
        ]

    def run_make(
        self,
        target,
        deployment="staging",
        *,
        entry=None,
        environment=None,
        check=True,
    ):
        self.log.write_text("", encoding="utf-8")
        self.ps_count.unlink(missing_ok=True)
        process_environment = os.environ.copy()
        for name in (
            "DOCKER_BUILD_FLAGS",
            "FAKE_REDIS_RUNNING",
            "FAKE_REDIS_SAVE_FAIL",
            "FAKE_REDIS_SAVE_RESPONSE",
            "FAKE_FINAL_RUNNING",
            "FAKE_CONTAINER_IDS",
            "FAKE_EXIT_CODE",
            "RELEASE_VERSION",
        ):
            process_environment.pop(name, None)
        process_environment.update(
            {
                "COMPOSE_PROJECT_NAME": "existing-stack",
                "FAKE_DOCKER_LOG": str(self.log),
                "FAKE_DOCKER_PS_COUNT": str(self.ps_count),
                **(environment or {}),
            }
        )
        result = subprocess.run(
            self.make_arguments(target, deployment, entry),
            env=process_environment,
            check=check,
            capture_output=True,
            text=True,
        )
        records = [
            json.loads(line)
            for line in self.log.read_text(encoding="utf-8").splitlines()
        ]
        return result, records

    def assert_compose_prefix(self, records):
        commands = []
        for record in records:
            if record.get("event") == "preflight":
                commands.append(record)
                continue
            arguments = record["args"]
            if arguments[0] == "compose":
                self.assertEqual(
                    arguments[:3],
                    ["compose", "--project-directory", str(self.project)],
                )
                self.assertEqual(arguments.count("--project-directory"), 1)
                self.assertNotIn("--project-name", arguments)
                self.assertNotIn("-p", arguments)
                self.assertEqual(record["project_name"], "existing-stack")
                commands.append(arguments[3:])
            else:
                commands.append(arguments)
        return commands

    def test_deploy_uses_physical_project_directory_in_every_environment(self):
        for deployment in ("dev", "test", "staging", "prod"):
            for entry in (self.project, self.alias):
                with self.subTest(deployment=deployment, entry=entry.name):
                    _, records = self.run_make("deploy", deployment, entry=entry)
                    self.assertEqual(records.pop(0), {"event": "preflight"})
                    commands = self.assert_compose_prefix(records)
                    files = ["-f", "base.yml"]
                    if deployment == "prod":
                        files += ["-f", "staging.yml", "-f", "prod.yml"]
                    else:
                        files += ["-f", f"{deployment}.yml"]
                    expected = [
                        files + ["config"],
                        ["build", "--pull", "--parallel"],
                        ["pull", "-q", "db", "redis", "elasticsearch"],
                    ]
                    if deployment != "dev":
                        expected.append(["pull", "-q", "nginx"])
                    expected += [
                        ["up", "-d", "--quiet-pull"],
                        ["exec", "server", "inv", "prepare"],
                    ]
                    self.assertEqual(commands, expected)
                    self.assertFalse(
                        list(self.secrets.glob("borg_replication_*")),
                        "application recreated retired Borg push secrets",
                    )

    def test_compose_render_uses_release_updated_in_same_invocation(self):
        bin_directory = self.root / "bin"
        bin_directory.mkdir()
        fake_git = bin_directory / "git"
        fake_git.write_text(
            "#!/bin/sh\nprintf '%s\\n' new-release\n", encoding="utf-8"
        )
        fake_git.chmod(0o755)

        envreplace = self.project / "deploy/scripts/envreplace"
        shutil.copy(ROOT / "deploy/scripts/envreplace", envreplace)
        envreplace.chmod(0o755)
        (self.project / ".env").write_text(
            "RELEASE_VERSION=old-release\n", encoding="utf-8"
        )

        _, records = self.run_make(
            "docker-compose.yml",
            environment={"PATH": f"{bin_directory}:{os.environ['PATH']}"},
        )

        config_record = next(
            record for record in records if "config" in record.get("args", [])
        )
        self.assertEqual(config_record["release_version"], "new-release")
        self.assertEqual(
            (self.project / ".env").read_text(encoding="utf-8"),
            "RELEASE_VERSION=new-release\n",
        )

    def test_stop_uses_physical_project_directory_and_ordered_shutdown(self):
        for deployment in ("dev", "test", "staging", "prod"):
            for entry in (self.project, self.alias):
                with self.subTest(deployment=deployment, entry=entry.name):
                    _, records = self.run_make("stop", deployment, entry=entry)
                    commands = self.assert_compose_prefix(records)
                    expected = []
                    if deployment in ("staging", "prod"):
                        expected.append(["stop", "--timeout", "120", "nginx"])
                    expected += [
                        ["stop", "--timeout", "180", "scheduler"],
                        ["stop", "--timeout", "180", "worker"],
                        ["stop", "--timeout", "180", "server"],
                        ["ps", "--status", "running", "--services"],
                        [
                            "exec",
                            "-T",
                            "redis",
                            "redis-cli",
                            "-s",
                            "/data/redis.sock",
                            "SAVE",
                        ],
                        ["stop", "--timeout", "120"],
                        ["ps", "--status", "running", "--services"],
                        ["ps", "--all", "--quiet"],
                    ]
                    self.assertEqual(commands, expected)

    def test_stop_skips_redis_save_when_redis_is_stopped(self):
        _, records = self.run_make(
            "stop", environment={"FAKE_REDIS_RUNNING": "0"}
        )
        commands = self.assert_compose_prefix(records)
        self.assertFalse(any("SAVE" in command for command in commands))

    def test_stop_fails_closed_when_redis_save_fails(self):
        result, records = self.run_make(
            "stop",
            environment={"FAKE_REDIS_SAVE_FAIL": "1"},
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        commands = self.assert_compose_prefix(records)
        self.assertNotIn(["stop", "--timeout", "120"], commands)

    def test_stop_rejects_unexpected_redis_save_response(self):
        result, records = self.run_make(
            "stop",
            environment={"FAKE_REDIS_SAVE_RESPONSE": "QUEUED"},
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        commands = self.assert_compose_prefix(records)
        self.assertNotIn(["stop", "--timeout", "120"], commands)

    def test_stop_fails_when_a_service_remains_running(self):
        result, _ = self.run_make(
            "stop",
            environment={"FAKE_FINAL_RUNNING": "elasticsearch"},
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Services still running", result.stderr)

    def test_stop_reports_containers_forced_to_exit(self):
        result, records = self.run_make(
            "stop",
            environment={"FAKE_CONTAINER_IDS": "container-1", "FAKE_EXIT_CODE": "137"},
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required SIGKILL", result.stderr)
        commands = self.assert_compose_prefix(records)
        self.assertIn(
            [
                "inspect",
                "--format",
                "{{.Name}} {{.State.ExitCode}}",
                "container-1",
            ],
            commands,
        )

    def test_stop_refuses_to_regenerate_missing_compose_file(self):
        (self.project / "docker-compose.yml").unlink()
        result, records = self.run_make("stop", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("docker-compose.yml is required", result.stderr)
        self.assertEqual(records, [])

    def test_build_storage_prerequisites_are_environment_specific(self):
        for deployment in ("staging", "prod", "dev"):
            with self.subTest(deployment=deployment):
                arguments = self.make_arguments("build", deployment)
                arguments.insert(2, "-n")
                result = subprocess.run(
                    arguments,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                if deployment == "dev":
                    self.assertIn("chmod 0777", result.stdout)
                else:
                    self.assertNotIn("chmod 0777", result.stdout)

    def test_development_defaults_to_persistent_secret_directory(self):
        application_root = self.root / "application"
        (application_root / "docker/secrets").mkdir(parents=True)
        arguments = [
            "make",
            "--no-print-directory",
            "-n",
            "-C",
            str(self.project),
            "build",
            "DEPLOY_ENVIRONMENT=dev",
            f"COMSES_APP_ROOT={application_root}",
            f"COMSES_SHARED_ROOT={self.shared}",
            f"COMSES_POSTGRES_ROOT={self.root / 'pgdata'}",
        ]
        environment = os.environ.copy()
        environment.pop("COMSES_SECRETS_ROOT", None)
        result = subprocess.run(
            arguments,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        expected = application_root / "docker/secrets/download_analytics_hmac_key"
        self.assertIn(str(expected), result.stdout)
        self.assertNotIn(str(application_root / "build/secrets"), result.stdout)


class ComposeRuntimeContractTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("docker"):
            self.skipTest("Docker Compose CLI unavailable")
        if subprocess.run(["docker", "compose", "version"], capture_output=True).returncode:
            self.skipTest("Docker Compose CLI unavailable")

        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="comses-compose-runtime-"
        )
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        for name in (
            "base.yml",
            "dev.yml",
            "test.yml",
            "staging.yml",
            "prod.yml",
            "e2e.yml",
            "recovery.yml",
        ):
            shutil.copy(ROOT / name, self.root / name)
        (self.root / ".env").write_text(
            "DB_USER=comsesnet\nDB_NAME=comsesnet\nES_VERSION=9.5.5\n"
            "RELEASE_VERSION=fixture\n",
            encoding="utf-8",
        )
        self.environment = os.environ.copy()
        self.environment.update(
            {
                "COMSES_APP_ROOT": str(self.root),
                "COMSES_SHARED_ROOT": str(self.root / "shared"),
                "COMSES_POSTGRES_ROOT": str(self.root / "pgdata"),
                "COMSES_LOG_ROOT": str(self.root / "logs"),
                "COMSES_SECRETS_ROOT": str(self.root / "secrets"),
                "DB_USER": "comsesnet",
                "DB_NAME": "comsesnet",
                "ES_VERSION": "9.5.5",
                "RELEASE_VERSION": "fixture",
                "UBUNTU_MIRROR": "archive.ubuntu.com",
            }
        )

    def render(self, overlays, profile=None):
        command = [
            "docker",
            "compose",
            "--project-directory",
            str(self.root),
            "-f",
            str(self.root / "base.yml"),
        ]
        command.extend(
            argument
            for overlay in overlays
            for argument in ("-f", str(self.root / overlay))
        )
        if profile:
            command.extend(("--profile", profile))
        command.extend(("config", "--format", "json"))
        result = subprocess.run(
            command,
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            check=True,
        )
        (self.root / "docker-compose.yml").write_text(
            result.stdout, encoding="utf-8"
        )
        return json.loads(result.stdout)["services"]

    def assert_application_services(self, services):
        server = services["server"]
        worker = services["worker"]
        scheduler = services["scheduler"]
        for service in (worker, scheduler):
            self.assertEqual(service["image"], server["image"])
            self.assertIs(service["init"], True)
            self.assertNotIn("build", service)
            self.assertEqual(service.get("ports"), None)
            self.assertEqual(service["secrets"], server["secrets"])
            self.assertEqual(
                service["environment"]["DB_USER"],
                server["environment"]["DB_USER"],
            )
            self.assertEqual(
                service["environment"]["DB_NAME"],
                server["environment"]["DB_NAME"],
            )
            targets = {mount["target"] for mount in service["volumes"]}
            self.assertTrue({"/shared", "/shared/logs", "/etc/environment"} <= targets)
        self.assertEqual(worker["command"], ["/code/deploy/huey.sh"])
        self.assertEqual(scheduler["command"], ["/usr/local/bin/comses-scheduler"])

    def test_all_deployments_share_one_image_with_separate_processes(self):
        cases = (
            (("dev.yml",), None),
            (("test.yml",), "test-disabled"),
            (("staging.yml",), None),
            (("staging.yml", "prod.yml"), None),
        )
        for overlays, profile in cases:
            with self.subTest(overlays=overlays, profile=profile):
                services = self.render(overlays, profile=profile)
                self.assert_application_services(services)

    def test_dev_worker_waits_for_django_initialization(self):
        services = self.render(("dev.yml",))
        self.assertEqual(
            services["worker"]["depends_on"]["server"]["condition"],
            "service_healthy",
        )
        self.assertIn("healthcheck", services["server"])

    def test_storage_verifier_covers_shared_app_mounts(self):
        cases = (
            ("dev", ("dev.yml",)),
            ("test", ("test.yml",)),
            ("staging", ("staging.yml",)),
            ("prod", ("staging.yml", "prod.yml")),
        )
        for environment, overlays in cases:
            with self.subTest(environment=environment):
                self.render(overlays)
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "deploy/scripts/verify-compose-storage"),
                    ],
                    cwd=self.root,
                    env=self.environment | {"DEPLOY_ENVIRONMENT": environment},
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=result.stdout + result.stderr,
                )

    def test_e2e_and_recovery_hold_worker_and_scheduler(self):
        test = self.render(("test.yml",))
        self.assertNotIn("worker", test)
        self.assertNotIn("scheduler", test)

        e2e = self.render(("dev.yml", "e2e.yml"))
        self.assertNotIn("worker", e2e)
        self.assertNotIn("scheduler", e2e)
        e2e = self.render(("dev.yml", "e2e.yml"), profile="e2e-disabled")
        self.assertEqual(e2e["worker"]["profiles"], ["e2e-disabled"])
        self.assertEqual(e2e["scheduler"]["profiles"], ["e2e-disabled"])

        recovery_overlays = ("staging.yml", "prod.yml", "recovery.yml")
        recovery = self.render(recovery_overlays, profile="recovery-disabled")
        self.assertEqual(recovery["server"]["entrypoint"], ["/bin/sleep"])
        self.assertEqual(recovery["server"]["command"], ["infinity"])
        self.assertEqual(recovery["worker"]["profiles"], ["recovery-disabled"])
        self.assertEqual(recovery["scheduler"]["profiles"], ["recovery-disabled"])

    def test_cron_schedule_keeps_utc_cadences(self):
        schedule = (ROOT / "django/deploy/comses.cron").read_text(
            encoding="utf-8"
        )
        self.assertIn("CRON_TZ=UTC", schedule)
        for cadence in (
            "17 * * * * root",
            "25 6 * * * root",
            "47 6 * * 0 root",
        ):
            self.assertIn(cadence, schedule)
        self.assertNotIn("prune", schedule)


if __name__ == "__main__":
    unittest.main()
