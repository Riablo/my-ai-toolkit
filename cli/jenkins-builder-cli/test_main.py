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
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
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
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="jenkins-cli-test-")
        self.addCleanup(directory.cleanup)
        for name, value in (("CONFIG_DIR", Path(directory.name)), ("CONFIG_PATH", Path(directory.name) / "config.yaml")):
            patcher = patch.object(MODULE, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    @unittest.skipUnless(shutil.which("zsh"), "Zsh is unavailable")
    def test_zsh_tab_completes_subcommand_options_and_arguments(self) -> None:
        # Exercise real ZLE Tab completion; syntax checks miss word-position bugs.
        master, slave = pty.openpty()
        proc = subprocess.Popen(["zsh", "-f"], stdin=slave, stdout=slave, stderr=slave,
                                start_new_session=True, env={**os.environ, "TERM": "xterm-256color",
                                "JBC_TEST_COMPLETIONS": str(MODULE_PATH.parent)})
        os.close(slave)

        def read_output(marker=None):
            output = b""
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.2)[0]:
                    output += os.read(master, 65536)
                    if marker and marker in output:
                        break
                elif output and marker is None:
                    break
            if marker:
                self.assertIn(marker, output, output.decode(errors="replace"))
            return output.decode(errors="replace")

        try:
            read_output()
            setup = "PS1=JBC'_READY> '; fpath=(\"$JBC_TEST_COMPLETIONS\" $fpath); autoload -Uz compinit; compinit -D; bindkey '^I' expand-or-complete; bindkey '^X' send-break\n"
            os.write(master, setup.encode())
            read_output(b"JBC_READY> ")
            for command, expected in [
                ("build --", ["--job", "--branch", "--follow", "--json"]),
                ("build --job '文件夹/编辑器' --", ["--branch", "--follow", "--json"]),
                ("set-branch --", ["--job", "--branch", "--json"]),
                ("config init --", ["--url", "--username", "--token", "--verify-ssl"]),
                ("jobs list --", ["--query", "--json"]),
                ("jobs label job ", ["test", "prod"]),
                ("runs status job#1 --", ["--json"]),
            ]:
                with self.subTest(command=command):
                    # Never submit the command; cancel its editable line after Tab.
                    os.write(master, ("jenkins-builder-cli " + command + "\t\t").encode())
                    output = read_output()
                    for option in expected:
                        self.assertIn(option, output)
                os.write(master, b"\x18")
                read_output(b"JBC_READY> ")
        finally:
            proc.kill()
            proc.wait(timeout=5)
            os.close(master)

    @unittest.skipUnless(shutil.which("fish"), "Fish is unavailable")
    def test_fish_only_scans_jobs_at_the_job_argument(self) -> None:
        source = Path(__file__).with_name("jenkins-builder-cli.fish").read_text()
        source = source.replace('set -l cfg "$HOME/.config/jenkins-builder-cli/config.yaml"', 'set -l cfg "$JBC_TEST_CONFIG"')
        source = source.replace('function __jbc_emit_configured_jobs\n', 'function __jbc_emit_configured_jobs\n    set -g JBC_TEST_SCANS (math $JBC_TEST_SCANS + 1)\n')
        with tempfile.TemporaryDirectory(prefix="jenkins-completion-test-") as directory:
            config_path = Path(directory) / "config.yaml"
            config_path.write_text("jobs:\n  target:\n    label: test\n    description: chosen\n")
            for command, expected in [("jobs ", 0), ("jobs list ", 0), ("build ", 0), ("build --json ", 0), ("build --job ", 1), ("build --branch main --job ", 1), ("set-branch --job ", 1), ("set-branch --branch ", 0), ("jobs desc ", 1), ("jobs label ", 1), ("jobs label target ", 0)]:
                with self.subTest(command=command):
                    script = source + f"\nset -g JBC_TEST_SCANS 0\ncomplete -C 'jenkins-builder-cli {command}' >/dev/null\necho $JBC_TEST_SCANS\n"
                    result = subprocess.run(["fish", "--no-config", "-c", script], env={**os.environ, "JBC_TEST_CONFIG": str(config_path)}, capture_output=True, text=True, check=True)
                    self.assertEqual(result.stdout.strip(), str(expected))
            config_path.write_text("jobs:\n  文件夹/编辑器 with space:\n    label: prod\n    description: |\n      功能说明:\n        这里不是 job:\n  '123':\n    label: ''\n    description: ''\n")
            script = source + "\nset -g JBC_TEST_SCANS 0\n__jbc_emit_configured_jobs\n"
            result = subprocess.run(["fish", "--no-config", "-c", script], env={**os.environ, "JBC_TEST_CONFIG": str(config_path)}, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.splitlines(), ["文件夹/编辑器 with space\tJob · 正式服", "123\tJob · 未分类"])

    def make_config(self):
        config = MODULE.default_config()
        config["jenkins"].update(url="https://jenkins.example.com", username="mock", token="mock")
        return config

    def live_job(self, name="文件夹/编辑器"):
        return dict(full_name=name, url=MODULE.canonical_job_url("https://jenkins.example.com", name),
                    class_name="hudson.model.FreeStyleProject", color="blue", buildable=True)

    def branch_xml(self):
        return '<project><!--keep--><scm class="hudson.plugins.git.GitSCM"><branches><hudson.plugins.git.BranchSpec><name>*/main</name></hudson.plugins.git.BranchSpec></branches></scm></project>'

    def test_build_writes_literal_branch_before_triggering_with_server_defaults(self) -> None:
        # Jenkins 2.462.3: a parameterized job's /build requires submitted form
        # JSON; /buildWithParameters creates values from the job's defaults.
        for parameterized, status in ((False, 201), (True, 201), (True, 303)):
            with self.subTest(parameterized=parameterized, status=status):
                config = self.make_config()
                client = MODULE.JenkinsClient(config)
                entry = MODULE.job_entries_from_live_jobs(config, [self.live_job()])[0]
                properties = [{"_class": "hudson.model.ParametersDefinitionProperty"}] if parameterized else []
                client.get_json = Mock(return_value={"property": properties})
                initial_xml = self.branch_xml().replace("*/main", "${WORKFLOW_REVISION}" if parameterized else "*/main")
                client.job_config_xml = Mock(return_value=initial_xml)
                client.wait_for_build_number = Mock(return_value=42)
                client._crumb_headers = {}
                expected_url = entry.url + ("/buildWithParameters" if parameterized else "/build")
                saved_xml = []

                def respond(url, **kwargs):
                    response = MODULE.requests.Response()
                    if url == entry.url + "/config.xml":
                        saved_xml.append(kwargs["data"].decode("utf-8"))
                        response.status_code = 200
                        response._content = b""
                        return response
                    self.assertEqual(len(saved_xml), 1, "必须先写入 job 分支再触发构建")
                    branch, _, _ = MODULE.parse_branch_specifier(saved_xml[0])
                    self.assertEqual(branch, "*/v6.1.0")
                    self.assertNotIn("${WORKFLOW_REVISION}", saved_xml[0])
                    response.status_code = status if url == expected_url else 400
                    response._content = b"" if url == expected_url else b"<html><h1>HTTP Status 400 - Bad Request</h1><p>Nothing is submitted</p></html>"
                    if url == expected_url:
                        response.headers["Location"] = "https://jenkins.example.com/queue/item/9/"
                    return response

                client.session.post = Mock(side_effect=respond)
                with patch.object(MODULE, "create_client_and_entries", return_value=(config, client, [entry])), patch.object(MODULE.sys.stdin, "isatty", return_value=True), patch("builtins.input", side_effect=["1", "1", "v6.1.0"]), contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as error:
                    result = MODULE.main(["build", "--json"])
                self.assertEqual(result, 0, error.getvalue())
                self.assertEqual(json.loads(output.getvalue())["queue_id"], "9")
                self.assertEqual([call.args[0] for call in client.session.post.call_args_list], [entry.url + "/config.xml", expected_url])
                self.assertIsNone(client.session.post.call_args.kwargs["data"])
                self.assertIsNone(client.session.post.call_args.kwargs["params"])
                self.assertFalse(client.session.post.call_args.kwargs["allow_redirects"])

    def test_build_does_not_post_when_parameter_metadata_is_unavailable(self) -> None:
        for response in ({}, {"property": None}, {"property": [None]}, MODULE.CLIError("HTTP 403")):
            with self.subTest(response=response):
                client = MODULE.JenkinsClient(self.make_config())
                client.get_json = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
                client.session.post = Mock()
                with self.assertRaises(MODULE.CLIError):
                    client.trigger_build(self.live_job()["url"])
                client.session.post.assert_not_called()

    def test_doctor_and_every_jobs_command_sync_the_full_list(self) -> None:
        commands = [
            ["doctor", "--json"], ["jobs", "--json"], ["jobs", "list", "--query", "新增", "--json"],
            ["jobs", "label", "保留", "test", "--json"], ["jobs", "unlabel", "保留", "--json"],
            ["jobs", "desc", "保留", "新描述，含中文与空格 hello", "--json"], ["jobs", "desc", "保留", "", "--json"],
        ]
        for argv in commands:
            with self.subTest(argv=argv):
                config = self.make_config()
                config["jobs"] = {"保留": {"label": "prod", "aliases": ["旧描述", "用途"]}, "删除": {"label": "test", "description": "过期"}}
                MODULE.save_config(config)
                client = Mock()
                client.list_jobs.return_value = [self.live_job("保留"), self.live_job("新增")]
                client.job_config_xml.return_value = self.branch_xml()
                with patch.object(MODULE, "JenkinsClient", return_value=client), contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(MODULE.main(argv), 0)
                result = json.loads(output.getvalue())
                saved = MODULE.yaml.safe_load(MODULE.CONFIG_PATH.read_text())
                self.assertEqual(set(saved["jobs"]), {"保留", "新增"})
                self.assertEqual(saved["jobs"]["新增"], {"label": "", "description": ""})
                label = "test" if "label" in argv else "" if "unlabel" in argv else "prod"
                description = argv[3] if "desc" in argv else "旧描述；用途"
                self.assertEqual(saved["jobs"]["保留"], {"label": label, "description": description})
                self.assertEqual(MODULE.CONFIG_PATH.stat().st_mode & 0o777, 0o600)
                client.list_jobs.assert_called_once()
                client.find_job.assert_not_called()
                if argv[0] == "doctor":
                    self.assertEqual(result["missing_descriptions"], ["新增"])
                    self.assertEqual(result["status"], "ok")
                    self.assertNotIn("token", result)

    def test_doctor_only_reminds_about_missing_descriptions(self) -> None:
        config = self.make_config()
        config["jobs"] = {"unlabel": {"label": "", "description": "故意不分组"}, "empty": {"label": "prod", "description": ""}}
        MODULE.save_config(config)
        client = Mock()
        client.list_jobs.return_value = [self.live_job("unlabel"), self.live_job("empty")]
        with patch.object(MODULE, "JenkinsClient", return_value=client), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(MODULE.main(["doctor"]), 0)
        self.assertIn("- empty", output.getvalue())
        self.assertNotIn("unlabel", output.getvalue())
        self.assertNotIn("未分类", output.getvalue())

    def test_sync_failure_preserves_config_and_empty_success_removes_jobs(self) -> None:
        config = self.make_config()
        config["jobs"] = {"keep": {"label": "prod", "description": "保留"}}
        MODULE.save_config(config)
        original = MODULE.CONFIG_PATH.read_bytes()
        client = MODULE.JenkinsClient(config)
        folder = {"url": "https://jenkins.example.com/job/folder/", "_class": "com.cloudbees.hudson.plugins.folder.Folder"}
        for responses in ([MODULE.CLIError("HTTP 401")], [{"jobs": [folder]}, MODULE.CLIError("HTTP 403")], [{}], [{"jobs": [{}]}]):
            with self.subTest(responses=responses):
                client.get_json = Mock(side_effect=responses)
                with patch.object(MODULE, "JenkinsClient", return_value=client), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(MODULE.main(["doctor"]), 1)
                self.assertEqual(MODULE.CONFIG_PATH.read_bytes(), original)
        client.get_json = Mock(return_value={"jobs": []})
        with patch.object(MODULE, "JenkinsClient", return_value=client), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MODULE.main(["doctor"]), 0)
        self.assertEqual(MODULE.load_config()["jobs"], {})

    def test_doctor_rejects_invalid_config_before_network_or_write(self) -> None:
        invalid = [None, [], {"jobs": []}, {"jenkins": []}, {"jobs": {"job": "bad"}},
                   {"jobs": {"job": {"description": []}}}, {"jobs": {"job": {"label": "other"}}}]
        for section, key, value in [("jenkins", "url", "ftp://example.com"), ("jenkins", "url", "https://x:bad"),
                                    ("jenkins", "username", " "), ("jenkins", "token", 123),
                                    ("jenkins", "token", ""), ("jenkins", "verify_ssl", "false"),
                                    ("defaults", "timeout_seconds", 0), ("defaults", "poll_interval_seconds", -1)]:
            config = self.make_config()
            config[section][key] = value
            invalid.append(config)
        for config in invalid:
            with self.subTest(config=config):
                MODULE.CONFIG_PATH.write_text(MODULE.yaml.safe_dump(config))
                original = MODULE.CONFIG_PATH.read_bytes()
                with patch.object(MODULE, "JenkinsClient") as client, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(MODULE.main(["doctor"]), 1)
                client.assert_not_called()
                self.assertEqual(MODULE.CONFIG_PATH.read_bytes(), original)
        MODULE.CONFIG_PATH.write_text('jenkins:\n  token: [SECRET\n')
        with contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(MODULE.main(["doctor"]), 1)
        self.assertNotIn("SECRET", error.getvalue())
        MODULE.CONFIG_PATH.unlink()
        with contextlib.redirect_stderr(io.StringIO()) as error:
            self.assertEqual(MODULE.main(["doctor"]), 1)
        self.assertIn("config init", error.getvalue())

    def test_atomic_save_preserves_original_on_write_failure(self) -> None:
        MODULE.save_config(self.make_config())
        original = MODULE.CONFIG_PATH.read_bytes()
        with patch.object(MODULE.yaml, "safe_dump", side_effect=OSError("disk full")), self.assertRaises(OSError):
            MODULE.save_config(self.make_config())
        self.assertEqual(MODULE.CONFIG_PATH.read_bytes(), original)
        self.assertEqual(list(MODULE.CONFIG_DIR.iterdir()), [MODULE.CONFIG_PATH])

    def test_build_and_set_branch_argument_matrix(self) -> None:
        for command in ("build", "set-branch"):
            for has_job in (False, True):
                for has_branch in (False, True):
                    for empty_branch in ((False, True) if command == "build" and not has_job and not has_branch else (False,)):
                        with self.subTest(command=command, has_job=has_job, has_branch=has_branch, empty=empty_branch):
                            config = self.make_config()
                            config["jobs"] = {"文件夹/编辑器": {"label": "prod", "description": "自然语言描述"},
                                              "test-job": {"label": "test", "description": "测试"}}
                            MODULE.save_config(config)
                            client = Mock()
                            client.list_jobs.return_value = [self.live_job("文件夹/编辑器"), self.live_job("test-job"), self.live_job("unlabel")]
                            client.find_job.return_value = self.live_job()
                            client.job_config_xml.return_value = self.branch_xml()
                            client.trigger_build.return_value = "9"
                            client.wait_for_build_number.return_value = 42
                            client.wait_for_build_result.return_value = {"building": False, "result": "SUCCESS"}
                            argv = [command, "--json"]
                            if command == "build":
                                argv.append("--follow")
                            if has_job:
                                argv.extend(["--job", "文件夹/编辑器"])
                            if has_branch:
                                argv.extend(["--branch", "feature/中文"])
                            answers = [] if has_job else ["2", "1"]
                            prompts_branch = not has_branch and (command == "set-branch" or not has_job)
                            if prompts_branch:
                                answers.append("" if empty_branch else "feature/中文")
                            with patch.object(MODULE, "JenkinsClient", return_value=client), patch.object(MODULE.sys.stdin, "isatty", return_value=bool(answers)), patch("builtins.input", side_effect=answers) as prompt, contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as error:
                                self.assertEqual(MODULE.main(argv), 0)
                            payload = json.loads(output.getvalue())
                            self.assertEqual(payload["job"], "文件夹/编辑器")
                            self.assertEqual(prompt.call_count, len(answers))
                            self.assertEqual("当前分支: */main" in error.getvalue(), prompts_branch)
                            if not has_job:
                                self.assertIn("1. 测试服\n2. 正式服\n3. 未分类\n", error.getvalue())
                                self.assertIn("1. 文件夹/编辑器 — 自然语言描述", error.getvalue())
                            changes_branch = has_branch or (prompts_branch and not empty_branch)
                            self.assertEqual(client.update_job_config_xml.call_count, int(changes_branch))
                            if changes_branch:
                                xml = client.update_job_config_xml.call_args.args[1]
                                self.assertIn("*/feature/中文", xml)
                                self.assertIn("<!--keep-->", xml)
                            if command == "build":
                                client.trigger_build.assert_called_once_with(self.live_job()["url"])
                                client.wait_for_build_result.assert_called_once()
                                self.assertEqual(payload["status"], "completed")
                                calls = [call[0] for call in client.mock_calls]
                                if changes_branch:
                                    self.assertLess(calls.index("update_job_config_xml"), calls.index("trigger_build"))
                            else:
                                client.trigger_build.assert_not_called()
                            if has_job:
                                client.list_jobs.assert_not_called()

    def test_branch_failure_never_triggers_build(self) -> None:
        MODULE.save_config(self.make_config())
        for xml, failure in [("<flow-definition/>", None), ("<broken", None), (self.branch_xml(), MODULE.CLIError("HTTP 403"))]:
            client = Mock()
            client.find_job.return_value = self.live_job()
            client.job_config_xml.return_value = xml
            client.update_job_config_xml.side_effect = failure
            with patch.object(MODULE, "JenkinsClient", return_value=client), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(MODULE.main(["build", "--job", "文件夹/编辑器", "--branch", "release"]), 1)
            client.trigger_build.assert_not_called()

    def test_missing_arguments_without_tty_fail_before_network(self) -> None:
        for argv in (["build"], ["build", "--branch", "main"], ["set-branch"], ["set-branch", "--job", "job"], ["set-branch", "--branch", "main"]):
            with self.subTest(argv=argv), patch.object(MODULE.sys.stdin, "isatty", return_value=False), patch.object(MODULE, "JenkinsClient") as client, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(MODULE.main(argv), 1)
            client.assert_not_called()

    def test_interactive_validation_and_cancellation(self) -> None:
        entries = MODULE.job_entries_from_live_jobs(self.make_config(), [self.live_job()])
        with patch.object(MODULE.sys.stdin, "isatty", return_value=True), patch("builtins.input", side_effect=["x", "0", "1", "2", "1"]), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(MODULE.interactive_select_job(entries).full_name, "文件夹/编辑器")
        client = Mock()
        client.job_config_xml.return_value = self.branch_xml()
        with patch.object(MODULE.sys.stdin, "isatty", return_value=True), patch("builtins.input", side_effect=["", "main"]), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(MODULE.prompt_branch(client, entries[0]), "main")
        MODULE.save_config(self.make_config())
        client.list_jobs.return_value = [self.live_job()]
        with patch.object(MODULE, "JenkinsClient", return_value=client), patch.object(MODULE.sys.stdin, "isatty", return_value=True), patch("builtins.input", side_effect=EOFError), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(MODULE.main(["build"]), 130)
        client.trigger_build.assert_not_called()

    def test_old_commands_and_empty_flags_are_rejected(self) -> None:
        for argv in (["config", "edit"], ["config", "check"], ["config", "auth"], ["jobs", "alias"],
                     ["build", "old-name"], ["set-branch", "old-name", "main"],
                     ["build", "--job", ""], ["build", "--job", "job", "--branch", " "]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                MODULE.build_parser().parse_args(argv)
            self.assertEqual(error.exception.code, 2)

    def test_jobs_query_fetches_xml_only_for_matches(self) -> None:
        config = self.make_config()
        config["jobs"] = {"job-42": {"description": "selected", "label": "prod"}}
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

    def test_exact_job_name_does_not_enumerate(self) -> None:
        config = self.make_config()
        config["jobs"] = {"other": {"description": "target"}}
        client = MODULE.JenkinsClient(config)
        client.get_json = Mock(return_value={"fullName": "target", "_class": "hudson.model.FreeStyleProject", "buildable": True})
        client.list_jobs = Mock(side_effect=AssertionError("must not enumerate"))
        with patch.object(MODULE, "load_config", return_value=config), patch.object(MODULE, "JenkinsClient", return_value=client):
            _, _, entries = MODULE.create_client_and_entries(job_name="target")
        self.assertEqual(MODULE.resolve_job_name("target", entries).full_name, "target")
        client.get_json.assert_called_once()

    def test_unknown_job_still_enumerates_for_suggestions(self) -> None:
        config = self.make_config()
        client = Mock()
        client.find_job.return_value = None
        client.list_jobs.return_value = []
        with patch.object(MODULE, "load_config", return_value=config), patch.object(MODULE, "JenkinsClient", return_value=client):
            _, _, entries = MODULE.create_client_and_entries(job_name="unknown")
        client.list_jobs.assert_called_once()
        with self.assertRaises(MODULE.CLIError):
            MODULE.resolve_job_name("unknown", entries)

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

    def test_only_exact_names_resolve_including_chinese(self) -> None:
        config = self.make_config()
        config["jobs"] = {"文件夹/正式服 编辑器2.0": {"description": "编辑器", "label": "prod"}}
        entries = MODULE.job_entries_from_live_jobs(config, [self.live_job("文件夹/正式服 编辑器2.0")])
        self.assertEqual(MODULE.resolve_job_name("文件夹/正式服 编辑器2.0", entries).full_name, "文件夹/正式服 编辑器2.0")
        for value in ("编辑器", "正式服", "1"):
            with self.subTest(value=value), self.assertRaises(MODULE.CLIError):
                MODULE.resolve_job_name(value, entries)
        url = MODULE.canonical_job_url("https://jenkins.example.com/jenkins", entries[0].full_name)
        self.assertIn("%E6%96%87", url)
        self.assertIn("%20", url)
        self.assertEqual(MODULE.extract_full_name_from_job_url("https://jenkins.example.com/jenkins", url), entries[0].full_name)

    def test_normalize_job_meta_migrates_legacy_config(self) -> None:
        self.assertEqual(MODULE.normalize_job_meta({"label": "prod", "aliases": ["前端正式", "frontend prod", "前端正式"]}),
                         {"label": "prod", "description": "前端正式；frontend prod"})
        self.assertEqual(MODULE.normalize_job_meta({"env": "test", "keywords": "前端测试, frontend test"}),
                         {"label": "test", "description": "前端测试；frontend test"})
        for description in ("", "自然语言描述"):
            self.assertEqual(MODULE.normalize_job_meta({"aliases": ["old"], "description": description}),
                             {"label": "", "description": description})
        self.assertEqual(MODULE.normalize_job_meta({}), {"label": "", "description": ""})

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
