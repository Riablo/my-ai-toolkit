# /// script
# requires-python = ">=3.10"
# dependencies = ["requests", "pyyaml"]
# ///
from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).with_name("main.py")
SPEC = importlib.util.spec_from_file_location("jenkins_builder_cli_main", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("无法加载 jenkins-builder-cli main.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class JenkinsBuilderCliTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("fish"), "Fish is unavailable")
    def test_fish_only_scans_jobs_at_the_job_argument(self) -> None:
        source = Path(__file__).with_name("jenkins-builder-cli.fish").read_text()
        source = source.replace('set -l cfg "$HOME/.config/jenkins-builder-cli/config.yaml"', 'set -l cfg "$JBC_TEST_CONFIG"')
        source = source.replace('function __jbc_emit_configured_jobs\n', 'function __jbc_emit_configured_jobs\n    set -g JBC_TEST_SCANS (math $JBC_TEST_SCANS + 1)\n')
        with tempfile.TemporaryDirectory(prefix="jenkins-completion-test-") as directory:
            config_path = Path(directory) / "config.yaml"
            config_path.write_text("jobs:\n  target:\n    label: test\n    aliases:\n    - chosen\n")
            for command, expected in [("jobs ", 0), ("jobs list ", 0), ("jobs alias ", 0), ("build ", 1), ("build --json ", 1), ("jobs alias add ", 1), ("jobs label ", 1), ("jobs label target ", 0)]:
                with self.subTest(command=command):
                    script = source + f"\nset -g JBC_TEST_SCANS 0\ncomplete -C 'jenkins-builder-cli {command}' >/dev/null\necho $JBC_TEST_SCANS\n"
                    result = subprocess.run(["fish", "--no-config", "-c", script], env={**os.environ, "JBC_TEST_CONFIG": str(config_path)}, capture_output=True, text=True, check=True)
                    self.assertEqual(result.stdout.strip(), str(expected))

    def make_config(self):
        config = MODULE.default_config()
        config["jenkins"].update(url="https://jenkins.example.com", username="mock", token="mock")
        return config

    def test_jobs_query_fetches_xml_only_for_matches(self) -> None:
        config = self.make_config()
        config["jobs"] = {"job-42": {"aliases": ["selected"], "label": "prod"}}
        client = Mock()
        client.list_jobs.return_value = [
            dict(full_name=f"job-{n}", url=f"https://jenkins.example.com/job/job-{n}",
                 class_name="hudson.model.FreeStyleProject", color="blue", buildable=True)
            for n in range(100)
        ]
        client.job_config_xml.return_value = '<project><scm class="hudson.plugins.git.GitSCM"><branches><hudson.plugins.git.BranchSpec><name>*/main</name></hudson.plugins.git.BranchSpec></branches></scm></project>'
        for query in ("job-42", "selected", "正式服", "no-match"):
            client.job_config_xml.reset_mock()
            with self.subTest(query=query), patch.object(MODULE, "load_config", return_value=config), patch.object(MODULE, "JenkinsClient", return_value=client), contextlib.redirect_stdout(io.StringIO()) as output:
                MODULE.cmd_jobs_list(SimpleNamespace(query=query, json=True))
            result = json.loads(output.getvalue())
            self.assertEqual(client.job_config_xml.call_count, len(result))
            self.assertEqual([item["full_name"] for item in result], [] if query == "no-match" else ["job-42"])

    def test_exact_job_name_wins_over_alias_without_enumerating(self) -> None:
        config = self.make_config()
        config["jobs"] = {"other": {"aliases": ["target"]}}
        client = MODULE.JenkinsClient(config)
        client.get_json = Mock(return_value={"fullName": "target", "_class": "hudson.model.FreeStyleProject", "buildable": True})
        client.list_jobs = Mock(side_effect=AssertionError("must not enumerate"))
        with patch.object(MODULE, "load_config", return_value=config), patch.object(MODULE, "JenkinsClient", return_value=client):
            _, _, entries = MODULE.create_client_and_entries(ref="target")
        self.assertEqual(MODULE.resolve_job_ref("target", entries).full_name, "target")
        client.get_json.assert_called_once()

    def test_alias_resolution_ignores_deleted_owner_without_enumerating(self) -> None:
        config = self.make_config()
        config["jobs"] = {"removed": {"aliases": ["chosen"]}, "live": {"aliases": ["chosen"]}}
        client = MODULE.JenkinsClient(config)
        client.get_json = Mock(side_effect=[
            MODULE.CLIError("missing", status_code=404),
            MODULE.CLIError("missing", status_code=404),
            {"fullName": "live", "_class": "hudson.model.FreeStyleProject", "buildable": True},
        ])
        client.list_jobs = Mock(side_effect=AssertionError("must not enumerate"))
        with patch.object(MODULE, "load_config", return_value=config), patch.object(MODULE, "JenkinsClient", return_value=client):
            _, _, entries = MODULE.create_client_and_entries(ref="chosen")
        self.assertEqual(MODULE.resolve_job_ref("chosen", entries).full_name, "live")

    def test_unknown_job_still_enumerates_for_suggestions(self) -> None:
        config = self.make_config()
        client = Mock()
        client.find_job.return_value = None
        client.list_jobs.return_value = []
        with patch.object(MODULE, "load_config", return_value=config), patch.object(MODULE, "JenkinsClient", return_value=client):
            _, _, entries = MODULE.create_client_and_entries(ref="unknown")
        client.list_jobs.assert_called_once()
        with self.assertRaises(MODULE.CLIError):
            MODULE.resolve_job_ref("unknown", entries)

    def test_follow_uses_server_byte_cursor_and_preserves_tail_and_final_text(self) -> None:
        config = self.make_config()
        client = MODULE.JenkinsClient(config)
        responses = []
        # Byte cursors may include annotations absent from the decoded text;
        # empty polls retain the cursor, and a truncated log may reset it.
        for text, cursor, more in [("old\n中文\n", 100, True), ("", 100, True), ("追加\n", 120, True), ("reset\n", 6, True), ("尾行", 12, False)]:
            response = MODULE.requests.Response()
            response.status_code = 200
            response._content = text.encode("utf-8")
            response.headers["X-Text-Size"] = str(cursor)
            if more:
                response.headers["X-More-Data"] = "true"
            responses.append(response)
        client.session.get = Mock(side_effect=responses)
        client.build_info = Mock(side_effect=AssertionError("no status polling needed"))
        with patch.object(MODULE, "load_config", return_value=config), patch.object(MODULE, "JenkinsClient", return_value=client), patch.object(MODULE.time, "sleep"), contextlib.redirect_stdout(io.StringIO()) as output:
            MODULE.cmd_logs(SimpleNamespace(run_id="job#1", json=False, follow=True, tail=1))
        self.assertEqual(output.getvalue(), "中文\n追加\nreset\n尾行\n")
        self.assertEqual([call.kwargs["params"]["start"] for call in client.session.get.call_args_list], [0, 100, 100, 120, 6])
        self.assertTrue(all(call.args[0].endswith("/logText/progressiveText") for call in client.session.get.call_args_list))

    def test_progressive_console_rejects_missing_cursor(self) -> None:
        client = MODULE.JenkinsClient(self.make_config())
        response = MODULE.requests.Response()
        response.status_code = 200
        response._content = b"text"
        client.session.get = Mock(return_value=response)
        with self.assertRaisesRegex(MODULE.CLIError, "X-Text-Size"):
            client.progressive_console("https://jenkins.example.com/job/test", 1, 0)

    def run_tail_pages(self, pages, tail):
        client = Mock()
        client.base_url = "https://jenkins.example.com"
        client.progressive_console.side_effect = pages
        with patch.object(MODULE, "load_config", return_value=self.make_config()), patch.object(MODULE, "JenkinsClient", return_value=client), patch.object(MODULE.time, "sleep") as sleep, contextlib.redirect_stdout(io.StringIO()) as output:
            MODULE.cmd_logs(SimpleNamespace(run_id="job#1", json=False, follow=True, tail=tail))
        return output.getvalue(), client, sleep

    def test_follow_tail_drains_all_initial_pages_before_output(self) -> None:
        first = "".join(f"line-{n}\n" for n in range(1, 10001))
        second = "".join(f"line-{n}\n" for n in range(10001, 20001))
        end = len(first) + len(second)
        output, client, sleep = self.run_tail_pages([
            (first, len(first), True),
            (second, end, True),
            ("", end, True),  # Caught up, but the build is still running.
            ("new output\n", end + 11, True),
            ("final output\n", end + 24, False),
        ], 10)
        self.assertEqual(output, "".join(f"line-{n}\n" for n in range(19991, 20001)) + "new output\nfinal output\n")
        self.assertEqual([call.args[2] for call in client.progressive_console.call_args_list], [0, len(first), end, end, end + 11])
        self.assertEqual(sleep.call_count, 2)

    def test_follow_tail_on_already_completed_log_exits_after_first_page(self) -> None:
        output, client, sleep = self.run_tail_pages([("old\nlast\n", 9, False)], 1)
        self.assertEqual(output, "last\n")
        client.progressive_console.assert_called_once()
        sleep.assert_not_called()

    def test_follow_without_tail_drains_initial_pages_before_sleeping(self) -> None:
        client = Mock()
        client.base_url = "https://jenkins.example.com"
        pages = iter([("first\n", 6, True), ("second\n", 13, True), ("", 13, True), ("last\n", 18, False)])
        events = []

        def read_page(*args):
            events.append("read")
            return next(pages)

        client.progressive_console.side_effect = read_page
        with patch.object(MODULE, "load_config", return_value=self.make_config()), patch.object(MODULE, "JenkinsClient", return_value=client), patch.object(MODULE.time, "sleep", side_effect=lambda _: events.append("sleep")), contextlib.redirect_stdout(io.StringIO()) as output:
            MODULE.cmd_logs(SimpleNamespace(run_id="job#1", json=False, follow=True, tail=None))
        self.assertEqual(output.getvalue(), "first\nsecond\nlast\n")
        self.assertEqual(events, ["read", "read", "read", "sleep", "read"])

    def test_follow_tail_empty_initial_page_does_not_end_active_follow(self) -> None:
        output, _, sleep = self.run_tail_pages([("", 0, True), ("later\n", 6, False)], 1)
        self.assertEqual(output, "later\n")
        sleep.assert_called_once()

    def test_follow_tail_discards_old_pages_after_cursor_reset(self) -> None:
        output, _, _ = self.run_tail_pages([
            ("old-a\nold-b\n", 100, True),
            ("新", 3, True),
            ("内容\r", 10, True),
            ("\nlast", 15, False),
        ], 3)
        self.assertEqual(output, "新内容\nlast\n")

    def test_non_follow_logs_keeps_partial_last_line_and_tail(self) -> None:
        client = Mock()
        client.base_url = "https://jenkins.example.com"
        client.console_text.return_value = "old\n\nlast"
        with patch.object(MODULE, "load_config", return_value=self.make_config()), patch.object(MODULE, "JenkinsClient", return_value=client), contextlib.redirect_stdout(io.StringIO()) as output:
            MODULE.cmd_logs(SimpleNamespace(run_id="job#1", json=False, follow=False, tail=2))
        self.assertEqual(output.getvalue(), "\nlast\n")
        client.build_info.assert_not_called()

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

    def test_resolve_job_ref_accepts_exact_job_name_and_alias(self) -> None:
        entries = [
            MODULE.JobEntry(
                full_name="folder/frontend-build",
                url="https://jenkins/job/folder/job/frontend-build",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={
                    "label": "test",
                    "aliases": ["前端测试服", "frontend test"],
                },
            ),
            MODULE.JobEntry(
                full_name="folder/frontend-prod",
                url="https://jenkins/job/folder/job/frontend-prod",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={
                    "label": "prod",
                    "aliases": ["前端正式服", "frontend prod"],
                },
            ),
        ]

        matched = MODULE.resolve_job_ref("folder/frontend-build", entries)
        self.assertEqual(matched.full_name, "folder/frontend-build")
        matched = MODULE.resolve_job_ref("前端测试服", entries)
        self.assertEqual(matched.full_name, "folder/frontend-build")

    def test_resolve_job_ref_rejects_non_exact_name(self) -> None:
        entries = [
            MODULE.JobEntry(
                full_name="folder/frontend-build",
                url="https://jenkins/job/folder/job/frontend-build",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={},
            ),
            MODULE.JobEntry(
                full_name="folder/frontend-release",
                url="https://jenkins/job/folder/job/frontend-release",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={},
            ),
        ]

        with self.assertRaises(MODULE.CLIError):
            MODULE.resolve_job_ref("frontend", entries)

    def test_resolve_job_ref_rejects_ambiguous_alias(self) -> None:
        entries = [
            MODULE.JobEntry(
                full_name="folder/frontend-build",
                url="https://jenkins/job/folder/job/frontend-build",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={"aliases": ["前端"]},
            ),
            MODULE.JobEntry(
                full_name="folder/frontend-release",
                url="https://jenkins/job/folder/job/frontend-release",
                class_name="hudson.model.FreeStyleProject",
                color="blue",
                buildable=True,
                metadata={"aliases": ["前端"]},
            ),
        ]

        with self.assertRaises(MODULE.CLIError):
            MODULE.resolve_job_ref("前端", entries)

    def test_normalize_job_meta_supports_new_and_legacy_config(self) -> None:
        self.assertEqual(
            MODULE.normalize_job_meta(
                {
                    "label": "prod",
                    "aliases": ["前端正式", "frontend prod"],
                    "description": "旧描述不再保留",
                }
            ),
            {
                "label": "prod",
                "aliases": ["前端正式", "frontend prod"],
            },
        )
        self.assertEqual(
            MODULE.normalize_job_meta(
                {
                    "env": "test",
                    "keywords": "前端测试, frontend test",
                }
            ),
            {
                "label": "test",
                "aliases": ["前端测试", "frontend test"],
            },
        )

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
