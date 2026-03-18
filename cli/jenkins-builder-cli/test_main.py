# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pyyaml"]
# ///
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("main.py")
SPEC = importlib.util.spec_from_file_location("jenkins_builder_cli_main", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("无法加载 jenkins-builder-cli main.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class JenkinsBuilderCliTests(unittest.TestCase):
    def test_job_url_roundtrip(self) -> None:
        base_url = "https://jenkins.example.com"
        full_name = "folder/api/build"
        job_url = MODULE.canonical_job_url(base_url, full_name)
        self.assertEqual(
            job_url,
            "https://jenkins.example.com/job/folder/job/api/job/build",
        )
        self.assertEqual(
            MODULE.extract_full_name_from_job_url(base_url, job_url),
            full_name,
        )

    def test_parse_run_id(self) -> None:
        full_name, number = MODULE.parse_run_id("folder/api#123")
        self.assertEqual(full_name, "folder/api")
        self.assertEqual(number, 123)
        with self.assertRaises(MODULE.CLIError):
            MODULE.parse_run_id("folder/api")

    def test_resolve_job_ref_requires_exact_job_name(self) -> None:
        entries = [
            MODULE.JobEntry(
                full_name="folder/frontend-build",
                url="https://jenkins/job/folder/job/frontend-build",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={
                    "env": "test",
                    "description": "测试服前端项目",
                    "keywords": "前端测试服",
                },
            ),
            MODULE.JobEntry(
                full_name="folder/frontend-prod",
                url="https://jenkins/job/folder/job/frontend-prod",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={
                    "env": "prod",
                    "description": "正式服前端项目",
                    "keywords": "前端正式服",
                },
            ),
        ]

        matched = MODULE.resolve_job_ref("folder/frontend-build", entries)
        self.assertEqual(matched.full_name, "folder/frontend-build")
        with self.assertRaises(MODULE.CLIError):
            MODULE.resolve_job_ref("前端测试服", entries)

    def test_resolve_job_ref_rejects_non_exact_name(self) -> None:
        entries = [
            MODULE.JobEntry(
                full_name="folder/frontend-build",
                url="https://jenkins/job/folder/job/frontend-build",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={"description": "前端 build"},
            ),
            MODULE.JobEntry(
                full_name="folder/frontend-release",
                url="https://jenkins/job/folder/job/frontend-release",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={"description": "前端 release"},
            ),
        ]

        with self.assertRaises(MODULE.CLIError):
            MODULE.resolve_job_ref("frontend", entries)

    def test_parse_branch_specifier(self) -> None:
        xml_text = """<?xml version='1.1' encoding='UTF-8'?>
<project>
  <actions/>
  <scm class="hudson.plugins.git.GitSCM" plugin="git@5.0.0">
    <configVersion>2</configVersion>
    <branches>
      <hudson.plugins.git.BranchSpec>
        <name>*/main</name>
      </hudson.plugins.git.BranchSpec>
    </branches>
  </scm>
</project>
"""
        current, tree, branch_node = MODULE.parse_branch_specifier(xml_text)
        self.assertEqual(current, "*/main")
        branch_node.text = "*/feature/login"
        xml_out = MODULE.serialize_tree(tree)
        self.assertIn("*/feature/login", xml_out)

    def test_job_entry_branch_display_uses_live_specifier(self) -> None:
        entry = MODULE.JobEntry(
            full_name="folder/test.frontend_build",
            url="https://jenkins/job/folder/job/test.frontend_build",
            class_name="hudson.model.FreeStyleProject",
            color="blue",
            buildable=True,
            metadata={},
            live_branch_specifier="*/release/5.9.34",
        )
        self.assertEqual(entry.branch_display, "*/release/5.9.34")

    def test_normalize_branch_specifier(self) -> None:
        self.assertEqual(MODULE.normalize_branch_specifier("v5.9.34"), "*/v5.9.34")
        self.assertEqual(MODULE.normalize_branch_specifier("*/v5.9.34"), "*/v5.9.34")

    def test_build_status_mapping(self) -> None:
        self.assertEqual(MODULE.build_status({"building": True, "result": None}), "running")
        self.assertEqual(MODULE.build_status({"building": False, "result": "SUCCESS"}), "completed")
        self.assertEqual(MODULE.build_status({"building": False, "result": "FAILURE"}), "failed")
        self.assertEqual(MODULE.build_status({"building": False, "result": "ABORTED"}), "aborted")
        self.assertEqual(MODULE.build_status({"building": False, "result": "UNSTABLE"}), "unstable")
        self.assertEqual(MODULE.build_status({"building": False, "result": "NOT_BUILT"}), "not_built")
        self.assertEqual(MODULE.build_status({"building": False, "result": None}), "unknown")

    def test_build_status_payload(self) -> None:
        payload = MODULE.build_status_payload(
            "folder/test.frontend_build",
            123,
            "https://jenkins.example.com/job/folder/job/test.frontend_build",
            {
                "building": False,
                "result": "SUCCESS",
                "displayName": "#123",
                "timestamp": 1700000000000,
                "duration": 12000,
                "estimatedDuration": 15000,
            },
        )
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["result"], "SUCCESS")
        self.assertEqual(payload["url"], "https://jenkins.example.com/job/folder/job/test.frontend_build/123/")
        self.assertEqual(payload["display_name"], "#123")
        self.assertEqual(payload["timestamp_ms"], 1700000000000)
        self.assertEqual(payload["duration_ms"], 12000)
        self.assertEqual(payload["estimated_duration_ms"], 15000)

    def test_stop_build_does_not_follow_redirects(self) -> None:
        config = MODULE.default_config()
        config["jenkins"].update(
            {
                "url": "https://jenkins.example.com",
                "username": "alice",
                "token": "token",
            }
        )
        client = MODULE.JenkinsClient(config)
        seen: dict[str, object] = {}

        def fake_post(path_or_url: str, **kwargs: object) -> object:
            seen["path_or_url"] = path_or_url
            seen.update(kwargs)
            return object()

        client.post = fake_post  # type: ignore[method-assign]
        client.stop_build("https://jenkins.example.com/job/test", 123)

        self.assertEqual(
            seen["path_or_url"],
            "https://jenkins.example.com/job/test/123/stop",
        )
        self.assertEqual(seen["expected_codes"], (200, 201, 302))
        self.assertFalse(seen["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
