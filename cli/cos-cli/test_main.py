import base64
import hashlib
import importlib.util
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("cos_cli_main", ROOT / "main.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config_path = self.root / "config.json"
        self.config = {
            **cli.default_config(),
            "secret_id": "fixture-secret-id",
            "secret_key": "fixture-secret-key",
            "security_token": "fixture-temporary-token",
            "bucket": "test-bucket-1234567890",
            "domain": "https://cdn.example.com/base/",
        }
        self.save_config()

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def file(self, name, content=b"image-fixture"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def invoke(self, *args, client=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        fake = client if client is not None else Mock()
        if client is None:
            fake.upload_file.return_value = {"ETag": '"etag-fixture"'}
        with (
            patch.object(cli, "create_client", return_value=fake) as factory,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = cli.main(["--config", str(self.config_path), *map(str, args)])
        return code, stdout.getvalue(), stderr.getvalue(), fake, factory

    def test_folder_md5_layout_filtering_and_url_encoding(self):
        photo = self.file("photos/旅行/海边 #1.JPG", b"photo")
        self.file("photos/ignore.txt")
        self.file("photos/nested/cover.webp")
        (self.root / "photos/loop").symlink_to(
            self.root / "photos", target_is_directory=True
        )
        (self.root / "photos/linked.png").symlink_to(photo)
        code, output, progress, fake, factory = self.invoke(
            self.root / "photos", "--dry-run", "--json"
        )
        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(payload["total"], 2)
        result = next(item for item in payload["results"] if item["file"] == str(photo))
        self.assertEqual(
            result["key"],
            f"imgs/photos/旅行/海边_#1.{hashlib.md5(b'photo').hexdigest()}.JPG",
        )
        self.assertIn("/base/imgs/photos/%E6%97%85%E8%A1%8C/", result["url"])
        self.assertIn("%231.", result["url"])
        self.assertEqual(result["content_type"], "image/jpeg")
        self.assertEqual(result["status"], "planned")
        self.assertNotIn("fingerprint", result)
        self.assertIn("未发起上传", progress)
        factory.assert_not_called()
        fake.upload_file.assert_not_called()

    def test_multiple_inputs_and_options_between_paths(self):
        a, b = self.file("a.png"), self.file("b.jpg")
        code, output, _, fake, _ = self.invoke(
            a, "--prefix", "blog pics", b, "--no-md5"
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            output.splitlines(),
            [
                "https://cdn.example.com/base/blog_pics/a.png",
                "https://cdn.example.com/base/blog_pics/b.jpg",
            ],
        )
        self.assertEqual(fake.upload_file.call_count, 2)
        self.assertEqual(
            fake.upload_file.call_args_list[0].kwargs,
            {
                "Bucket": "test-bucket-1234567890",
                "Key": "blog_pics/a.png",
                "LocalFilePath": str(a),
                "ContentType": "image/png",
                "EnableMD5": True,
            },
        )

    def test_root_prefix_default_domain_and_md5_override(self):
        self.config["domain"] = ""
        self.config["use_md5"] = False
        self.save_config()
        a = self.file("a.png", b"a")
        _, output, _, _, _ = self.invoke(a, "--prefix", "", "--dry-run")
        self.assertEqual(
            output.strip(),
            "https://test-bucket-1234567890.cos.ap-beijing.myqcloud.com/a.png",
        )
        _, output, _, _, _ = self.invoke(
            a, "--prefix", "", "--md5", "--dry-run", "--format", "key"
        )
        self.assertEqual(output.strip(), "a.0cc175b9c0f1b6a831c399e269772661.png")

    def test_all_files_and_unsupported_explicit_file(self):
        file = self.file("assets/data.txt")
        with self.assertRaisesRegex(cli.CLIError, "扩展名"):
            self.invoke(file, "--dry-run")
        code, output, _, _, _ = self.invoke(
            self.root / "assets",
            "--all-files",
            "--no-md5",
            "--dry-run",
            "--format",
            "key",
        )
        self.assertEqual((code, output.strip()), (0, "imgs/assets/data.txt"))

    def test_entire_batch_preflight_before_network(self):
        a = self.file("one/a b.png")
        b = self.file("two/a_b.png")
        for rest, message in (
            ([b], "Key 冲突"),
            ([self.root / "missing.png"], "路径不存在"),
        ):
            with self.subTest(rest=rest), patch.object(cli, "create_client") as factory:
                with self.assertRaisesRegex(cli.CLIError, message):
                    cli.main(
                        [
                            "--config",
                            str(self.config_path),
                            str(a),
                            *map(str, rest),
                            "--no-md5",
                        ]
                    )
                factory.assert_not_called()

    def test_duplicates_deduplicated_and_explicit_file_uses_basename(self):
        file = self.file("nested/a.png")
        _, output, _, fake, _ = self.invoke(file, file, "--no-md5", "--json")
        self.assertEqual(json.loads(output)["total"], 1)
        self.assertEqual(json.loads(output)["results"][0]["key"], "imgs/a.png")
        fake.upload_file.assert_called_once()

    def test_partial_failure_continues_and_does_not_leak_exception(self):
        files = [self.file(name) for name in ("a.png", "b.jpg", "c.webp")]
        fake = Mock()
        fake.upload_file.side_effect = [
            {"ETag": "one"},
            RuntimeError(
                "signed-url?q-signature=sensitive " + self.config["secret_key"]
            ),
            {"ETag": "three"},
        ]
        code, output, progress, _, _ = self.invoke(*files, "--json", client=fake)
        payload = json.loads(output)
        self.assertEqual((code, payload["uploaded"], payload["failed"]), (1, 2, 1))
        self.assertEqual(
            [item["status"] for item in payload["results"]],
            ["uploaded", "failed", "uploaded"],
        )
        self.assertEqual(fake.upload_file.call_count, 3)
        self.assertNotIn("signed-url", output + progress)
        self.assertNotIn(self.config["secret_key"], output + progress)

    def test_file_changed_after_plan_is_not_uploaded(self):
        file = self.file("a.png", b"before")
        fake = Mock()

        def factory(_):
            file.write_bytes(b"changed-after-planning")
            return fake

        stdout = io.StringIO()
        with (
            patch.object(cli, "create_client", side_effect=factory),
            redirect_stdout(stdout),
            redirect_stderr(io.StringIO()),
        ):
            code = cli.main(["--config", str(self.config_path), str(file), "--json"])
        self.assertEqual(code, 1)
        self.assertIn("发生变化", json.loads(stdout.getvalue())["results"][0]["error"])
        fake.upload_file.assert_not_called()

    def test_interruption_keeps_completed_results(self):
        files = [self.file(name) for name in ("a.png", "b.png", "c.png")]
        fake = Mock()
        fake.upload_file.side_effect = [{"ETag": "one"}, KeyboardInterrupt()]
        code, output, _, _, _ = self.invoke(*files, "--json", client=fake)
        payload = json.loads(output)
        self.assertEqual(code, 130)
        self.assertTrue(payload["interrupted"])
        self.assertEqual(payload["uploaded"], 1)
        self.assertEqual(fake.upload_file.call_count, 2)

    def test_missing_etag_is_not_reported_as_success(self):
        fake = Mock()
        fake.upload_file.return_value = {}
        code, output, progress, _, _ = self.invoke(self.file("a.png"), client=fake)
        self.assertEqual(code, 1)
        self.assertEqual(output, "")
        self.assertIn("ETag", progress)

    def test_symlink_empty_folder_and_unsafe_names(self):
        file = self.file("a.png")
        link = self.root / "link.png"
        link.symlink_to(file)
        empty = self.root / "empty"
        empty.mkdir()
        unsafe = self.file("bad\nname.png")
        for path, message in (
            (link, "符号链接"),
            (empty, "未找到"),
            (unsafe, "控制字符"),
        ):
            with self.subTest(path=path), self.assertRaisesRegex(cli.CLIError, message):
                self.invoke(path, "--dry-run")

    def test_markdown_escapes_labels_and_encodes_url(self):
        file = self.file("a[b](c)#%.png")
        _, output, _, _, _ = self.invoke(
            file, "--no-md5", "--dry-run", "--format", "markdown"
        )
        self.assertTrue(output.startswith("![a\\[b\\](c)#%](https://"))
        self.assertTrue(output.endswith("a%5Bb%5D%28c%29%23%25.png)\n"))

    def test_literal_leading_dash_after_double_dash(self):
        self.file("--photo.png")
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            code, output, _, _, _ = self.invoke(
                "--dry-run", "--no-md5", "--format", "key", "--", "--photo.png"
            )
        finally:
            os.chdir(previous)
        self.assertEqual((code, output.strip()), (0, "imgs/--photo.png"))

    def test_config_init_permissions_and_no_overwrite(self):
        path = self.root / "private/config.json"
        with redirect_stdout(io.StringIO()):
            cli.main(["config", "init", "--config", str(path)])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        original = path.read_bytes()
        with self.assertRaisesRegex(cli.CLIError, "已存在"):
            cli.init_config(path)
        self.assertEqual(path.read_bytes(), original)
        with self.assertRaisesRegex(cli.CLIError, "secret_id"):
            cli.load_config(path)

    def test_config_validation_and_redacted_show(self):
        for overrides in (
            {"secret_id": ""},
            {"secret_key": " bad"},
            {"bucket": "no-appid"},
            {"region": "bad/region"},
            {"use_md5": "false"},
            {"timeout": True},
            {"timeout": 0},
            {"prefix": "a/../b"},
            {"domain": "https://u:p@example.com"},
            {"domain": "https://example.com?x=1"},
            {"domain": "https://example.com:bad"},
            {"domain": "https://example.com#"},
            {"domain": "https://example.com?"},
            {"domain": "https://@example.com"},
            {"domain": 123},
            {"security_token": None},
            {"use_m5": True},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(cli.CLIError):
                cli.validate_config({**self.config, **overrides})
        for field in ("secret_id", "secret_key", "bucket", "region"):
            raw = self.config.copy()
            del raw[field]
            with (
                self.subTest(missing=field),
                self.assertRaisesRegex(cli.CLIError, field),
            ):
                cli.validate_config(raw)
        _, output, _, _, factory = self.invoke("config", "show")
        for field in cli.SECRET_FIELDS:
            self.assertEqual(json.loads(output)[field], "***")
            self.assertNotIn(self.config[field], output)
        factory.assert_not_called()

    def test_missing_or_malformed_config_reports_no_contents(self):
        with self.assertRaisesRegex(cli.CLIError, "config init"):
            cli.load_config(self.root / "absent.json")
        self.config_path.write_text(
            '{"secret_key": "DO-NOT-PRINT", broken}', encoding="utf-8"
        )
        with self.assertRaises(cli.CLIError) as caught:
            cli.load_config(self.config_path)
        self.assertIn("JSON 格式错误", str(caught.exception))
        self.assertNotIn("DO-NOT-PRINT", str(caught.exception))

    def test_real_sdk_builds_signed_https_put_with_md5_and_mime(self):
        import requests

        content = b"fixture PNG bytes"
        file = self.file("海边 #1.png", content)
        config = cli.validate_config(self.config)
        client = cli.create_client(config)
        captured = []

        def send(session, request, **kwargs):
            captured.append((request, kwargs, request.body.read()))
            response = requests.Response()
            response.status_code = 200
            response.headers["ETag"] = '"verified-etag"'
            response._content = b""
            response.request = request
            return response

        with patch.object(requests.Session, "send", autospec=True, side_effect=send):
            code, output, _, _, _ = self.invoke(
                file, "--no-md5", "--json", client=client
            )
        self.assertEqual(code, 0)
        request, options, uploaded = captured[0]
        headers = {
            key: value.decode() if isinstance(value, bytes) else value
            for key, value in request.headers.items()
        }
        self.assertEqual(request.method, "PUT")
        self.assertEqual(
            request.url,
            "https://test-bucket-1234567890.cos.ap-beijing.myqcloud.com/imgs/%E6%B5%B7%E8%BE%B9_%231.png",
        )
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(
            headers["Content-MD5"],
            base64.b64encode(hashlib.md5(content).digest()).decode(),
        )
        self.assertIn("q-signature=", headers["Authorization"])
        self.assertEqual(headers["x-cos-security-token"], self.config["security_token"])
        self.assertEqual(options["timeout"], 60)
        self.assertTrue(options["verify"])
        self.assertEqual(uploaded, content)
        self.assertEqual(json.loads(output)["results"][0]["etag"], '"verified-etag"')

    def test_sdk_access_denied_and_network_error_are_sanitized(self):
        import requests
        from qcloud_cos import CosServiceError

        error = CosServiceError(
            "PUT",
            {"code": "AccessDenied", "message": "DO-NOT-PRINT", "requestid": "req123"},
            403,
        )
        message = cli.upload_error(error, self.config)
        self.assertIn("AccessDenied", message)
        self.assertIn("403", message)
        self.assertIn("req123", message)
        self.assertNotIn("DO-NOT-PRINT", message)
        network_error = requests.ConnectionError(
            "https://signed-url?q-signature=DO-NOT-PRINT"
        )
        self.assertNotIn("DO-NOT-PRINT", cli.upload_error(network_error, self.config))

    def test_bash_entrypoint_resolves_relative_symlink_and_argument_errors(self):
        binary = self.root / "bin/cos-cli"
        binary.parent.mkdir()
        binary.symlink_to(os.path.relpath(ROOT / "cos-cli", binary.parent))
        help_result = subprocess.run(
            [str(binary), "--help"], capture_output=True, text=True, check=False
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("配置命令", help_result.stdout)
        result = subprocess.run(
            [str(binary), "--unknown"], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
