from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "codex_deepseek.py"
SPEC = importlib.util.spec_from_file_location("codex_deepseek_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MANAGER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MANAGER
SPEC.loader.exec_module(MANAGER)


class DeepSeekManagerTests(unittest.TestCase):
    def test_agent_defaults_to_max_reasoning(self):
        self.assertEqual(MANAGER.EFFORT, "max")
        self.assertIn('model_reasoning_effort = "max"', MANAGER.expected_agent_text())

    def test_codex_child_env_removes_codex_api_key_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = MANAGER.resolve_paths(temp_dir)
            with mock.patch.dict(
                os.environ,
                {"CODEX_API_KEY": "do-not-forward", "SAFE_TEST_VALUE": "kept"},
                clear=True,
            ):
                env = MANAGER.codex_child_env(paths)
        self.assertNotIn("CODEX_API_KEY", env)
        self.assertEqual(env["SAFE_TEST_VALUE"], "kept")

    def test_stage_windows_store_runtime_copies_codex_and_host(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resources = root / "OpenAI.Codex_1.2.3_x64__test" / "app" / "resources"
            resources.mkdir(parents=True)
            (resources / "codex.exe").write_bytes(b"codex")
            (resources / MANAGER.WINDOWS_CODE_MODE_HOST).write_bytes(b"host")
            (resources / MANAGER.WINDOWS_SANDBOX_SETUP).write_bytes(b"sandbox-setup")
            paths = MANAGER.resolve_paths(str(root / "home"))
            staged = MANAGER.stage_windows_store_runtime(resources / "codex.exe", paths)
            self.assertEqual(staged.read_bytes(), b"codex")
            self.assertEqual(
                staged.with_name(MANAGER.WINDOWS_CODE_MODE_HOST).read_bytes(),
                b"host",
            )
            self.assertEqual(
                staged.with_name(MANAGER.WINDOWS_SANDBOX_SETUP).read_bytes(),
                b"sandbox-setup",
            )

    def test_stage_windows_store_runtime_requires_sandbox_setup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            resources = root / "OpenAI.Codex_1.2.3_x64__test" / "app" / "resources"
            resources.mkdir(parents=True)
            (resources / "codex.exe").write_bytes(b"codex")
            (resources / MANAGER.WINDOWS_CODE_MODE_HOST).write_bytes(b"host")
            paths = MANAGER.resolve_paths(str(root / "home"))
            with self.assertRaises(MANAGER.ManagerError):
                MANAGER.stage_windows_store_runtime(resources / "codex.exe", paths)

    def test_executor_workchain_accepts_probe_file_and_token(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = MANAGER.resolve_paths(str(Path(temp_dir) / "home"))

            def fake_run(*args, **kwargs):
                command = args[0]
                workspace = Path(command[command.index("-C") + 1])
                (workspace / "prewalk_executor_probe.txt").write_text(
                    "EXECUTOR_PROBE_OK\n", encoding="utf-8"
                )
                return SimpleNamespace(
                    returncode=0,
                    stdout='{"type":"turn.completed"}\nWORKCHAIN_OK\n',
                    stderr="",
                )

            with mock.patch.object(MANAGER.subprocess, "run", side_effect=fake_run):
                outcome = MANAGER.executor_workchain_test(paths, "codex.exe")
            self.assertTrue(outcome["executor_workchain"])
            self.assertEqual(outcome["sandbox"], "workspace-write")

    def test_executor_workchain_rejects_missing_probe_file(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout="WORKCHAIN_OK\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = MANAGER.resolve_paths(str(Path(temp_dir) / "home"))
            with mock.patch.object(MANAGER.subprocess, "run", return_value=completed):
                with self.assertRaises(MANAGER.ManagerError):
                    MANAGER.executor_workchain_test(paths, "codex.exe")

    def test_native_test_accepts_executor_surface_pass_phrase(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout='{"type":"turn.completed"}\nagent message: NATIVE_DEEPSEEK_OK\n',
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = MANAGER.resolve_paths(temp_dir)
            with mock.patch.object(MANAGER.subprocess, "run", return_value=completed):
                result = MANAGER.native_test(paths, "codex.exe")
        self.assertTrue(result["desktop_fresh_session_native"])
        self.assertEqual(result["executor_surface"], "codex_exec")
        self.assertEqual(result["model_provider"], "deepseek")
        self.assertEqual(result["model"], "deepseek-flash")
        self.assertEqual(result["reasoning_effort"], "max")
        self.assertEqual(result["agent_role"], "DeepSeek")

    def test_native_test_rejects_missing_pass_phrase(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout="agent message: something else\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = MANAGER.resolve_paths(temp_dir)
            with mock.patch.object(MANAGER.subprocess, "run", return_value=completed):
                with self.assertRaises(MANAGER.ManagerError):
                    MANAGER.native_test(paths, "codex.exe")

    def test_normalizer_does_not_accept_other_text_changes(self):
        self.assertEqual(
            MANAGER.normalize_native_verification_message("NATIVE_DEEPSEEK_OK。"),
            "NATIVE_DEEPSEEK_OK",
        )
        self.assertNotEqual(
            MANAGER.normalize_native_verification_message("NATIVE_DEEPSEEK_OK extra."),
            "NATIVE_DEEPSEEK_OK",
        )


if __name__ == "__main__":
    unittest.main()
