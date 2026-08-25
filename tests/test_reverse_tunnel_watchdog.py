import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "scripts" / "watch_reverse_tunnels.sh"
BASH = shutil.which("bash") or r"C:\Program Files\Git\bin\bash.exe"


class ReverseTunnelWatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp = Path(self.tempdir.name)
        self.state_dir = self.temp / "state"
        self.kill_log = self.temp / "kill.log"
        self.bin_dir = self.temp / "bin"
        self.bin_dir.mkdir()
        self._write_stub(
            "curl",
            "#!/usr/bin/env bash\n"
            'test "${FAKE_CURL_RESULT:-healthy}" = "healthy"\n',
        )
        self._write_stub(
            "ss",
            "#!/usr/bin/env bash\n"
            'if [[ "$*" = *"state established"* ]]; then\n'
            '  if test "${FAKE_ACTIVE_CONNECTIONS:-absent}" = "present"; then\n'
            '    echo \'ESTAB 0 0 172.19.0.1:18288 172.19.0.2:45000\'\n'
            "  fi\n"
            'elif test "${FAKE_LISTENER:-present}" = "present"; then\n'
            '  echo \'LISTEN 0 128 172.19.0.1:18288 0.0.0.0:* users:(("sshd",pid=4242,fd=7))\'\n'
            "fi\n",
        )
        self._write_stub(
            "ps",
            "#!/usr/bin/env bash\n"
            'case "$*" in\n'
            '  *"user="*) echo "${FAKE_PROCESS_USER:-deploy}" ;;\n'
            '  *"comm="*) echo "${FAKE_PROCESS_COMMAND:-sshd}" ;;\n'
            '  *"args="*) echo "${FAKE_PROCESS_ARGS:-sshd: deploy}" ;;\n'
            "esac\n",
        )
        self._write_stub(
            "kill",
            "#!/usr/bin/env bash\n"
            'printf "%s\\n" "$*" >> "$WATCHDOG_KILL_LOG"\n',
        )
        self._write_stub("logger", "#!/usr/bin/env bash\nexit 0\n")
        self._write_stub("flock", "#!/usr/bin/env bash\nexit 0\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_stub(self, name: str, contents: str) -> None:
        path = self.bin_dir / name
        path.write_text(contents, encoding="utf-8", newline="\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def _run(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "WATCHDOG_STATE_DIR": self.state_dir.as_posix(),
                "WATCHDOG_CURL_BIN": (self.bin_dir / "curl").as_posix(),
                "WATCHDOG_SS_BIN": (self.bin_dir / "ss").as_posix(),
                "WATCHDOG_PS_BIN": (self.bin_dir / "ps").as_posix(),
                "WATCHDOG_KILL_BIN": (self.bin_dir / "kill").as_posix(),
                "WATCHDOG_LOGGER_BIN": (self.bin_dir / "logger").as_posix(),
                "WATCHDOG_FLOCK_BIN": (self.bin_dir / "flock").as_posix(),
                "WATCHDOG_KILL_LOG": self.kill_log.as_posix(),
            }
        )
        env.update(overrides)
        return subprocess.run(
            [BASH, SCRIPT.as_posix(), "--port", "18288"],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_healthy_probe_clears_prior_failure_without_killing(self):
        self.state_dir.mkdir()
        (self.state_dir / "18288.failures").write_text("1\n", encoding="ascii")

        result = self._run(FAKE_CURL_RESULT="healthy")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.state_dir / "18288.failures").exists())
        self.assertFalse(self.kill_log.exists())

    def test_one_failed_probe_records_state_without_killing(self):
        result = self._run(FAKE_CURL_RESULT="failed")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.state_dir / "18288.failures").read_text(encoding="ascii").strip(),
            "1",
        )
        self.assertFalse(self.kill_log.exists())

    def test_two_consecutive_failures_terminate_only_verified_deploy_sshd(self):
        self._run(FAKE_CURL_RESULT="failed")

        result = self._run(FAKE_CURL_RESULT="failed")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.kill_log.read_text(encoding="utf-8").strip(), "-TERM 4242")

    def test_active_upload_defers_stale_listener_cleanup(self):
        self._run(FAKE_CURL_RESULT="failed")

        result = self._run(
            FAKE_CURL_RESULT="failed",
            FAKE_ACTIVE_CONNECTIONS="present",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.kill_log.exists())
        self.assertEqual(
            (self.state_dir / "18288.failures").read_text(encoding="ascii").strip(),
            "2",
        )

    def test_unsafe_listener_is_never_terminated(self):
        self._run(FAKE_CURL_RESULT="failed")

        result = self._run(
            FAKE_CURL_RESULT="failed",
            FAKE_PROCESS_USER="root",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.kill_log.exists())

    def test_installer_wires_a_persistent_one_minute_timer(self):
        installer = (ROOT / "deploy" / "scripts" / "install_helpers.sh").read_text(
            encoding="utf-8"
        )
        timer_path = (
            ROOT
            / "deploy"
            / "systemd"
            / "lush-media-reverse-tunnel-watchdog.timer"
        )
        self.assertTrue(timer_path.exists(), "reverse tunnel watchdog timer is missing")
        timer = timer_path.read_text(encoding="utf-8")

        self.assertIn("lush-media-reverse-tunnel-watchdog.timer", installer)
        self.assertNotIn(
            'install -m 755 "${DEPLOY_DIR}/scripts/watch_reverse_tunnels.sh" '
            "/opt/lush-media-video/app/deploy/scripts/watch_reverse_tunnels.sh",
            installer,
        )
        self.assertIn("OnUnitActiveSec=1min", timer)
        self.assertIn("Persistent=true", timer)


if __name__ == "__main__":
    unittest.main()
