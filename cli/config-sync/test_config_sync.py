#!/usr/bin/env python3
"""Local fake SSH, real rsync: never contact a user's configured hosts."""

import fcntl
import json
import os
import pty
import re
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import termios
import time
import tomllib
import unittest
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
CLI = DIRECTORY / "config-sync"
BASH = shutil.which("bash")
RSYNC = os.environ.get("CONFIG_SYNC_TEST_RSYNC", shutil.which("rsync"))

FAKE_SSH = r'''
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
while args and args[0].startswith("-"):
    option = args.pop(0)
    if option in ("-o", "-l", "-p"):
        args.pop(0)
host = args.pop(0).split("@")[-1]
homes = json.loads(os.environ["TEST_REMOTE_HOMES"])
if host not in homes:
    sys.exit("Unexpected SSH host: " + host)
command = " ".join(args)
with open(os.environ["TEST_SSH_LOG"], "a") as log:
    log.write(json.dumps({"host": host, "command": command}) + "\n")
env = dict(os.environ, HOME=homes[host])
os.chdir(homes[host])
os.execve("/bin/sh", ["sh", "-c", command], env)
'''


class ConfigSyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="config-sync test ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.local = self.root / "local home"
        self.remotes = {host: self.root / f"{host} home" for host in ("home", "work")}
        self.bin = self.root / "bin"
        for directory in (self.local, self.bin, *self.remotes.values()):
            directory.mkdir()
        self.config = self.root / "xdg/config-sync/config.toml"
        self.config.parent.mkdir(parents=True)
        self.log = self.root / "ssh.jsonl"
        self.env = dict(
            os.environ,
            HOME=str(self.local),
            XDG_CONFIG_HOME=str(self.config.parent.parent),
            PATH=f"{self.bin}:{os.environ['PATH']}",
            TEST_REMOTE_HOMES=json.dumps({key: str(value) for key, value in self.remotes.items()}),
            TEST_SSH_LOG=str(self.log),
        )
        self.executable("ssh", f"#!{sys.executable}\n" + FAKE_SSH)
        (self.bin / "rsync").symlink_to(RSYNC)
        (self.bin / "config-sync").symlink_to(CLI)

    def executable(self, name, text):
        file = self.bin / name
        if file.is_symlink():
            file.unlink()
        file.write_text(text)
        file.chmod(0o755)

    def write(self, file, text):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
        return file

    def configure(self, text):
        self.config.write_text(text)

    def run_cli(self, *args, success=True, entry=CLI):
        result = subprocess.run(
            [BASH, str(entry), *args], env=self.env, text=True,
            capture_output=True, timeout=30,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def backup(self, target):
        return target.with_name(f".{target.name}.config-sync-backups")

    def snapshots(self, target):
        root = self.backup(target)
        return sorted(file for file in root.iterdir() if file.name != ".owner") if root.exists() else []

    def two_hosts(self):
        self.configure('''
[hosts.home.files]
htask = "~/.config/htask/config.toml"
[hosts.office]
ssh = "user@work"
[hosts.office.files]
htask = "~/.config/htask/config.toml"
''')
        source = self.write(self.local / ".config/htask/config.toml", "new-local")
        targets = [self.write(home / ".config/htask/config.toml", f"old-{host}")
                   for host, home in self.remotes.items()]
        return source, targets

    def test_init_creates_private_fully_commented_inactive_template(self):
        shutil.rmtree(self.config.parent)
        result = self.run_cli("init")
        self.assertIn(str(self.config), result.stdout)
        content = self.config.read_text()
        self.assertEqual(tomllib.loads(content), {})
        self.assertTrue(all(not line.strip() or line.startswith("#") for line in content.splitlines()))
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.config.parent.stat().st_mode), 0o700)
        self.assertIn('# [hosts.home.files]', content)
        self.assertIn('# [hosts.home.dirs]', content)
        self.assertIn('# [hosts.office.files]', content)
        for args in ((), ("clean",), ("list",), ("--_complete", "hosts")):
            self.run_cli(*args)
        self.assertEqual(self.calls(), [])
        self.run_cli("init", success=False)
        self.assertEqual(self.config.read_text(), content)

    def test_init_supports_default_home_and_custom_config_path(self):
        custom = self.root / "custom path/config.toml"
        self.run_cli("--config", str(custom), "init")
        self.assertEqual(tomllib.loads(custom.read_text()), {})
        self.assertFalse(self.config.exists())
        self.env.pop("XDG_CONFIG_HOME")
        self.run_cli("init")
        default = self.local / ".config/config-sync/config.toml"
        self.assertEqual(default.read_bytes(), custom.read_bytes())
        self.assertEqual(self.calls(), [])

    def test_init_never_overwrites_existing_files_directories_or_links(self):
        foreign = self.write(self.root / "foreign.toml", "keep-foreign")
        for kind in ("empty", "malformed", "directory", "symlink", "dangling-link"):
            with self.subTest(kind=kind):
                if self.config.is_symlink() or self.config.is_file():
                    self.config.unlink()
                elif self.config.exists():
                    self.config.rmdir()
                if kind in ("empty", "malformed"):
                    self.configure("" if kind == "empty" else "this is not TOML")
                    expected = self.config.read_bytes()
                elif kind == "directory":
                    self.config.mkdir()
                else:
                    self.config.symlink_to(foreign if kind == "symlink" else self.root / "missing.toml")
                result = self.run_cli("init", success=False)
                self.assertIn("不覆盖", result.stderr)
                if kind in ("empty", "malformed"):
                    self.assertEqual(self.config.read_bytes(), expected)
                elif kind == "directory":
                    self.assertTrue(self.config.is_dir())
                else:
                    self.assertTrue(self.config.is_symlink())
                self.assertEqual(foreign.read_text(), "keep-foreign")
                self.assertFalse((self.root / "missing.toml").exists())
        self.assertEqual(self.calls(), [])

    def test_init_rejects_sync_arguments_without_creating_config(self):
        for args in (("init", "htask"), ("init", "--host", "home"), ("init", "--dry-run")):
            with self.subTest(args=args):
                self.run_cli(*args, success=False)
                self.assertFalse(self.config.exists())
        self.assertEqual(self.calls(), [])

    def test_commented_examples_are_valid_when_uncommented(self):
        template = (DIRECTORY / "config.example.toml").read_text()
        uncommented = "\n".join(
            line[2:] if line.startswith("# [hosts.") or re.match(r"# [a-z]+ = ", line) else line
            for line in template.splitlines()
        )
        self.configure(uncommented)
        result = self.run_cli("list")
        self.assertIn("home (ssh home)  htask [files]", result.stdout)
        self.assertIn("home (ssh home)  zsh [files]", result.stdout)
        self.assertIn("home (ssh home)  scripts [dirs]", result.stdout)
        self.assertIn("office (ssh user@workstation)  htask [files]", result.stdout)
        self.assertIn("office (ssh user@workstation)  nvim [dirs]", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_bare_command_syncs_all_entries_and_host_filter_syncs_whole_host(self):
        self.configure('''
[hosts.home.files]
init = "~/home-only"
htask = "~/shared"
[hosts.home.dirs]
list = "~/settings"
[hosts.office]
ssh = "work"
[hosts.office.files]
other = ["~/shared", "~/renamed-shared"]
''')
        self.write(self.local / "home-only", "home-version-1")
        self.write(self.local / "shared", "shared-version-1")
        self.write(self.local / "settings/nested/file", "directory-version-1")
        self.run_cli()
        self.assertEqual((self.remotes["home"] / "home-only").read_text(), "home-version-1")
        self.assertEqual((self.remotes["home"] / "shared").read_text(), "shared-version-1")
        self.assertEqual((self.remotes["home"] / "settings/nested/file").read_text(), "directory-version-1")
        self.assertEqual((self.remotes["work"] / "renamed-shared").read_text(), "shared-version-1")
        self.assertFalse((self.remotes["work"] / "home-only").exists())
        self.assertFalse((self.remotes["work"] / "settings").exists())
        self.assertEqual((self.local / "shared").read_text(), "shared-version-1")
        self.write(self.local / "home-only", "home-version-2")
        self.write(self.local / "shared", "shared-version-2")
        self.write(self.local / "settings/nested/file", "directory-version-2")
        before = len(self.calls())
        self.run_cli("--host", "home")
        self.assertEqual((self.remotes["home"] / "home-only").read_text(), "home-version-2")
        self.assertEqual((self.remotes["home"] / "shared").read_text(), "shared-version-2")
        self.assertEqual((self.remotes["home"] / "settings/nested/file").read_text(), "directory-version-2")
        self.assertEqual((self.remotes["work"] / "renamed-shared").read_text(), "shared-version-1")
        self.assertEqual({call["host"] for call in self.calls()[before:]}, {"home"})

    def test_same_path_all_hosts_backup_and_checksum(self):
        source, targets = self.two_hosts()
        # Same length and mtime is the plausible wrong rsync quick-check result.
        targets[0].write_text("old-local")
        os.utime(source, (1700000000, 1700000000))
        os.utime(targets[0], (1700000000, 1700000000))
        self.run_cli()
        self.assertEqual([file.read_text() for file in targets], ["new-local", "new-local"])
        self.assertEqual([self.snapshots(file)[0].read_text() for file in targets], ["old-local", "old-work"])
        self.assertEqual({call["host"] for call in self.calls()}, {"home", "work"})
        self.assertEqual(stat.S_IMODE(self.backup(targets[0]).stat().st_mode), 0o700)
        self.assertEqual(self.backup(targets[0]).joinpath(".owner").read_text(), f"config-sync:v1:{targets[0]}\n")

    def test_host_selection_repeated_hosts_and_snapshots(self):
        source, targets = self.two_hosts()
        self.run_cli("-H", "home", "--host", "home")
        self.assertEqual(targets[0].read_text(), "new-local")
        self.assertEqual(targets[1].read_text(), "old-work")
        self.assertEqual(len(self.snapshots(targets[0])), 1)
        source.write_text("second-version")
        self.run_cli("-H", "home", "-H", "office")
        self.assertEqual([file.read_text() for file in targets], ["second-version"] * 2)
        self.assertEqual({file.read_text() for file in self.snapshots(targets[0])}, {"old-home", "new-local"})
        self.assertEqual([file.read_text() for file in self.snapshots(targets[1])], ["old-work"])

    def test_different_file_path_quoting_and_creation(self):
        source = self.write(self.local / "source ' 配置 $name.toml", "exact-content")
        source.chmod(0o600)
        # Metacharacters must stay literal in both SSH preparation and rsync.
        destination = "~/new parent/O'Brien $(touch PWN); [*].toml"
        self.configure(f"[hosts.home.files]\ncustom = {json.dumps([str(source), destination])}\n")
        target = self.remotes["home"] / destination[2:]
        self.run_cli()
        self.assertEqual(target.read_text(), "exact-content")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertFalse(self.backup(target).exists())
        self.assertFalse((self.remotes["home"] / "PWN").exists())
        source.write_text("replacement")
        self.run_cli()
        self.assertEqual(self.snapshots(target)[0].read_text(), "exact-content")
        self.run_cli("clean")
        self.assertFalse(self.backup(target).exists())
        self.assertEqual(target.read_text(), "replacement")

    def test_directory_slashes_mirror_whole_snapshot_and_links(self):
        source = self.local / "source folder"
        self.write(source / "nested/a.conf", "new-a")
        self.write(source / ".hidden", "new-hidden")
        (source / "link").symlink_to("nested/a.conf")
        destinations = [self.remotes["home"] / "different folder", self.remotes["home"] / "second folder"]
        for target in destinations:
            self.write(target / "nested/a.conf", "old-a")
            self.write(target / "obsolete", "old-only")
            self.write(target / ".old-hidden", "old-hidden")
        self.configure("[hosts.home.dirs]\n" + "\n".join(
            f"dir{index} = {json.dumps([str(source) + ('/' if index else ''), str(target) + ('/' if not index else '')])}"
            for index, target in enumerate(destinations)
        ))
        self.run_cli()
        for target in destinations:
            self.assertEqual({file.name for file in target.iterdir()}, {"nested", ".hidden", "link"})
            self.assertEqual((target / "nested/a.conf").read_text(), "new-a")
            self.assertEqual((target / ".hidden").read_text(), "new-hidden")
            self.assertTrue((target / "link").is_symlink())
            self.assertEqual(os.readlink(target / "link"), "nested/a.conf")
            old = self.snapshots(target)[0]
            self.assertEqual((old / "nested/a.conf").read_text(), "old-a")
            self.assertEqual((old / "obsolete").read_text(), "old-only")
            self.assertEqual((old / ".old-hidden").read_text(), "old-hidden")

    def test_empty_directory_creation_and_mirror_delete_remains_backed_up(self):
        (self.local / "empty").mkdir()
        self.configure('[hosts.home.dirs]\nempty = ["~/empty/", "~/new parent/empty/"]\n')
        target = self.remotes["home"] / "new parent/empty"
        self.run_cli()
        self.assertTrue(target.is_dir())
        self.assertEqual(list(target.iterdir()), [])
        self.assertFalse(self.backup(target).exists())
        self.write(target / "only-on-remote", "must-be-backed-up")
        outside = self.write(self.remotes["home"] / "outside/keep", "do-not-follow-link")
        (target / "link").symlink_to(outside.parent, target_is_directory=True)
        self.run_cli()
        self.assertEqual(list(target.iterdir()), [])
        snapshot = self.snapshots(target)[0]
        self.assertEqual((snapshot / "only-on-remote").read_text(), "must-be-backed-up")
        self.assertTrue((snapshot / "link").is_symlink())
        self.assertEqual(outside.read_text(), "do-not-follow-link")

    def test_local_file_symlink_sends_content(self):
        actual = self.write(self.local / "actual.toml", "linked-content")
        (self.local / "link.toml").symlink_to(actual)
        self.configure('[hosts.home.files]\nlinked = "~/link.toml"\n')
        self.run_cli()
        target = self.remotes["home"] / "link.toml"
        self.assertFalse(target.is_symlink())
        self.assertEqual(target.read_text(), "linked-content")

    def test_clean_all_only_configured_backup_paths_without_local_source(self):
        source, targets = self.two_hosts()
        self.run_cli()
        source.unlink()  # Cleanup does not require any of the original local files.
        unrelated = self.write(self.remotes["home"] / ".other.config-sync-backups/keep", "keep")
        result = self.run_cli("clean", "--dry-run")
        self.assertIn("home", result.stdout)
        self.assertIn("office", result.stdout)
        self.assertTrue(all(self.backup(file).exists() for file in targets))
        before = len(self.calls())
        self.run_cli("clean")
        self.assertEqual(len(self.calls()) - before, 2)
        self.assertFalse(any(self.backup(file).exists() for file in targets))
        self.assertEqual([file.read_text() for file in targets], ["new-local"] * 2)
        self.assertEqual(unrelated.read_text(), "keep")
        self.run_cli("clean")  # Nothing left to clean is also successful.

    def test_clean_filtered_host(self):
        _, targets = self.two_hosts()
        self.run_cli()
        self.run_cli("--config", str(self.config), "clean", "--host", "office")
        self.assertTrue(self.backup(targets[0]).exists())
        self.assertFalse(self.backup(targets[1]).exists())
        self.assertEqual([file.read_text() for file in targets], ["new-local"] * 2)

    def test_unowned_backup_directory_or_symlink_is_never_deleted(self):
        _, targets = self.two_hosts()
        target = targets[0]
        backup = self.backup(target)
        foreign = self.write(self.root / "foreign/keep", "do-not-delete")
        for kind in ("unmarked", "wrong-owner", "symlink", "marker-symlink"):
            with self.subTest(kind=kind):
                if backup.is_symlink():
                    backup.unlink()
                elif backup.exists():
                    shutil.rmtree(backup)
                if kind == "symlink":
                    backup.symlink_to(foreign.parent, target_is_directory=True)
                else:
                    self.write(backup / "keep", "unowned")
                    if kind == "wrong-owner":
                        self.write(backup / ".owner", "config-sync:v1:/wrong-path\n")
                    elif kind == "marker-symlink":
                        owner = self.write(self.root / "owner", f"config-sync:v1:{target}\n")
                        (backup / ".owner").symlink_to(owner)
                self.run_cli("clean", "-H", "home", success=False)
                self.run_cli("-H", "home", success=False)
                self.assertTrue(backup.exists())
                self.assertEqual(target.read_text(), "old-home")
                self.assertEqual(foreign.read_text(), "do-not-delete")
        self.assertTrue(all("--server" not in call["command"] for call in self.calls()))

    def test_remote_wrong_type_or_symlink_stops_before_transfer(self):
        self.write(self.local / "source", "new")
        self.configure('[hosts.home.files]\nfile = ["~/source", "~/target"]\n')
        target = self.remotes["home"] / "target"
        foreign = self.write(self.remotes["home"] / "foreign", "untouched")
        for kind in ("directory", "symlink"):
            with self.subTest(kind=kind):
                if target.exists():
                    target.rmdir()
                if kind == "directory":
                    target.mkdir()
                else:
                    target.symlink_to(foreign)
                self.run_cli(success=False)
                self.assertFalse(self.backup(target).exists())
                self.assertEqual(foreign.read_text(), "untouched")
        self.assertTrue(all("--server" not in call["command"] for call in self.calls()))

    def test_backup_failure_prevents_any_rsync(self):
        _, targets = self.two_hosts()
        self.executable("cp", "#!/bin/sh\nexit 44\n")
        self.run_cli(success=False)
        self.assertEqual([file.read_text() for file in targets], ["old-home", "old-work"])
        self.assertEqual(len(self.calls()), 1)
        self.assertNotIn("--server", self.calls()[0]["command"])

    def test_transfer_failure_keeps_backup_and_stops_later_hosts(self):
        _, targets = self.two_hosts()
        self.executable("rsync", "#!/bin/sh\nexit 23\n")
        result = self.run_cli(success=False)
        self.assertIn("备份保留", result.stderr)
        self.assertEqual(self.snapshots(targets[0])[0].read_text(), "old-home")
        self.assertEqual([file.read_text() for file in targets], ["old-home", "old-work"])
        self.assertFalse(self.backup(targets[1]).exists())
        self.assertEqual({call["host"] for call in self.calls()}, {"home"})

    def test_invalid_config_is_rejected_before_ssh_including_unselected_hosts(self):
        cases = (
            "[broken", 'host = "home"', "hosts = []", "[hosts.home]\nfile = {}",
            '[hosts.home]\nssh = "-bad"', '[hosts.home]\nssh = "home; echo bad"',
            '[hosts.home.files]\na = ["~/a"]', '[hosts.home.files]\na = ["~/a", 2]',
            '[hosts.home.files]\na = "relative"', '[hosts.home.dirs]\na = "/"',
            '[hosts.home.dirs]\na = "~/"', '[hosts.home.dirs]\na = "/tmp/../a"',
            '[hosts.home.files]\na = "~/a\\nb"',
            '[hosts.home.files]\na = "~/a"\n[hosts.home.dirs]\na = "~/b"',
            '[hosts.home.dirs]\na = "~/a"\nb = "~/a/b"',
            '[hosts.home.files]\na = "~/a.config-sync-backups/secret"',
            '[hosts.home.files]\na = "~/a"\n[hosts.bad.files]\nb = false',
            '[hosts.home.files]\na = "~/a"\n[hosts.alias]\nssh = "home"\n[hosts.alias.files]\nb = "~/a"',
        )
        for text in cases:
            with self.subTest(config=text):
                self.configure(text)
                self.run_cli("-H", "home", success=False)
                self.run_cli("clean", success=False)
                self.assertEqual(self.calls(), [])

    def test_complete_source_plan_is_checked_before_first_host(self):
        self.write(self.local / "good", "valid")
        for kind in ("files", "dirs"):
            with self.subTest(kind=kind):
                self.configure(f'''[hosts.home.files]
good = "~/good"
[hosts.office]
ssh = "work"
[hosts.office.{kind}]
bad = "~/missing"
''')
                self.run_cli(success=False)
                self.assertEqual(self.calls(), [])
        self.configure('[hosts.home.dirs]\nwrong = "~/good"\n')
        self.run_cli(success=False)
        self.assertEqual(self.calls(), [])

    def test_unknown_hosts_and_positional_arguments_are_rejected(self):
        self.two_hosts()
        for args in (("htask",), ("unknown",), ("-H", "unknown"), ("clean", "-H", "unknown"),
                     ("--host",), ("--config",), ("--bad",), ("--_complete", "items")):
            with self.subTest(args=args):
                self.run_cli(*args, success=False)
                self.assertEqual(self.calls(), [])
        self.configure('[hosts.home.files]\nhtask = "~/.config/htask/config.toml"\n[hosts.office]\nssh = "work"\n')
        self.run_cli("-H", "office")  # A configured host with no entries is a no-op.
        self.assertEqual(self.calls(), [])
        self.run_cli("-H", "home", "-H", "office")
        self.assertEqual({call["host"] for call in self.calls()}, {"home"})

    def test_host_filter_does_not_require_other_hosts_local_sources(self):
        self.write(self.local / "present", "selected-content")
        self.configure('''[hosts.home.files]
present = "~/present"
[hosts.office]
ssh = "work"
[hosts.office.files]
missing = "~/missing"
''')
        self.run_cli(success=False)
        self.assertEqual(self.calls(), [])
        self.run_cli("--host", "home")
        self.assertEqual((self.remotes["home"] / "present").read_text(), "selected-content")
        self.assertEqual({call["host"] for call in self.calls()}, {"home"})

    def test_empty_missing_config_and_dry_run_never_connect(self):
        for text in (None, "", "# just a comment\n", "[hosts.home]\n"):
            with self.subTest(config=text):
                if text is None:
                    self.config.unlink(missing_ok=True)
                else:
                    self.configure(text)
                for args in ((), ("clean",), ("list",), ("--help",)):
                    self.run_cli(*args)
                self.assertEqual(self.calls(), [])
        self.two_hosts()
        self.run_cli("--dry-run")
        self.run_cli("clean", "--dry-run")
        self.assertEqual(self.calls(), [])
        self.assertFalse(self.backup(self.remotes["home"] / ".config/htask/config.toml").exists())

    def test_list_and_dynamic_completion_allow_missing_source_and_custom_config(self):
        self.configure('[hosts.home.files]\nhtask = "~/missing"\n[hosts.office.dirs]\nnvim = "~/also-missing"\n')
        self.assertIn("htask [files]", self.run_cli("list").stdout)
        self.assertEqual(self.run_cli("--_complete", "hosts").stdout.splitlines(), ["home", "office"])
        custom = self.write(self.root / "custom config.toml", '[hosts.custom.files]\nother = "~/not-present"\n')
        code = '''
_arguments() { state=command; }
_describe() { local array=$2; print -rl -- "${(@P)array}"; }
compadd() { local array=$2; print -rl -- "${(@P)array}"; }
words=(config-sync --config "$2" --host "")
CURRENT=5
source "$1"
_config-sync_hosts
'''
        result = subprocess.run(
            ["zsh", "-fc", code, "zsh", str(DIRECTORY / "_config-sync"), str(custom)],
            env=self.env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([line.split(":")[0] for line in result.stdout.splitlines()],
                         ["init", "clean", "list", "custom"])
        self.assertEqual(self.calls(), [])

    def test_real_zsh_tab_completes_hosts_and_subcommands(self):
        self.configure('[hosts.home.files]\nhtask = "~/not-present"\n')
        master, slave = pty.openpty()
        process = subprocess.Popen(
            ["zsh", "-f", "-i"], env=self.env, stdin=slave, stdout=slave, stderr=slave,
            start_new_session=True, preexec_fn=lambda: fcntl.ioctl(slave, termios.TIOCSCTTY, 0),
        )
        os.close(slave)

        def read_until(needle):
            data = b""
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.1)[0]:
                    data += os.read(master, 65536)
                    if needle in data:
                        return data
            self.fail(f"等待终端输出 {needle!r} 超时：{data!r}")

        try:
            setup = (
                f"fpath=({json.dumps(str(DIRECTORY))} $fpath); autoload -Uz compinit; compinit -u -D; "
                'unsetopt BEEP; bindkey "^I" expand-or-complete; '
                'capture() { print -r -- "COMPLETED=$BUFFER"; BUFFER=""; zle .accept-line; }; '
                'zle -N capture; bindkey "^X" capture; print READY\n'
            )
            os.write(master, setup.encode())
            read_until(b"\r\nREADY\r\n")
            for prefix, ending, expected in (
                (b"config-sync --host ho", b"me ", b"config-sync --host home "),
                (b"config-sync in", b"it ", b"config-sync init "),
            ):
                os.write(master, prefix + b"\t")
                read_until(ending)
                os.write(master, b"\x18")
                captured = read_until(b"COMPLETED=")
                self.assertIn(b"COMPLETED=" + expected, captured)
            self.assertEqual(self.calls(), [])
        finally:
            os.close(master)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.send_signal(1)  # SIGHUP closes the interactive shell on test failure.
                process.wait(timeout=3)

    def test_installer_discovers_entry_completion_and_symlinked_parser(self):
        repo = self.root / "toolkit repo"
        tool = repo / "cli/config-sync"
        tool.mkdir(parents=True)
        for name in ("config-sync", "config.py", "_config-sync", "config.example.toml"):
            shutil.copy2(DIRECTORY / name, tool / name)
        scripts = repo / "scripts"
        scripts.mkdir()
        shutil.copy2(DIRECTORY.parents[1] / "scripts/install.sh", scripts / "install.sh")
        result = subprocess.run([BASH, str(scripts / "install.sh"), "--no-rc"],
                                env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.local / ".local/bin/config-sync"
        completion = self.local / ".zsh/completions/_config-sync"
        self.assertEqual(installed.resolve(), (tool / "config-sync").resolve())
        self.assertEqual(completion.resolve(), (tool / "_config-sync").resolve())
        self.run_cli("init", entry=installed)
        self.assertEqual(tomllib.loads(self.config.read_text()), {})
        self.assertEqual(self.config.read_bytes(), (tool / "config.example.toml").read_bytes())
        result = self.run_cli("list", entry=installed)
        self.assertIn("没有配置同步项", result.stdout)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
