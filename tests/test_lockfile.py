import json
import os
import threading

from engkit import fsutil, installer, lockfile
from engkit.errors import EngkitError
from tests.helpers import TempDirTest, skill_text, snapshot

ENTRY = {
    "source": "builtin",
    "ref": None,
    "path": None,
    "commit": None,
    "content_sha256": "a" * 64,
    "targets": ["claude"],
}
CORRUPT = (
    "{not json",
    '{"lock_version": 2, "skills": {}}',
    '{"lock_version": 1, "skills": {"a": {}}}',
)
GOOD = dict(ENTRY)
BAD_ENTRIES = (
    ("../x", {}),
    ("Bad_Name", {}),
    ("demo", {"source": 5}),
    ("demo", {"ref": 5}),
    ("demo", {"path": []}),
    ("demo", {"commit": 7}),
    ("demo", {"content_sha256": "x"}),
    ("demo", {"content_sha256": "G" * 64}),
    ("demo", {"targets": ["vim"]}),
    ("demo", {"targets": "claude"}),
)


class LockfileTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.root = self.make_project()
        self.path = lockfile.lock_file(self.root)

    def test_digest_is_order_independent_and_content_sensitive(self):
        one = lockfile.digest({"a": "1", "b": "2"})
        self.assertEqual(one, lockfile.digest({"b": "2", "a": "1"}))
        self.assertNotEqual(one, lockfile.digest({"a": "1", "b": "3"}))
        self.assertEqual(one, fsutil.sha256_bytes(b"a\x001\nb\x002\n"))

    def test_read_missing_creates_nothing(self):
        self.assertEqual(lockfile.read(self.root), {})
        self.assertFalse((self.root / ".engkit").exists())

    def test_transaction_writes_atomically_and_creates_engkit(self):
        with lockfile.transaction(self.root) as skills:
            skills["demo"] = dict(ENTRY)
        data = json.loads(self.path.read_text())
        self.assertEqual(data["lock_version"], 1)
        self.assertEqual(data["skills"]["demo"]["targets"], ["claude"])
        leftovers = sorted(os.listdir(self.root / ".engkit"))
        self.assertEqual(leftovers, ["skills.lock.json", "skills.lock.json.lock"])

    def test_failed_transaction_does_not_write(self):
        with self.assertRaises(RuntimeError), lockfile.transaction(self.root) as skills:
            skills["demo"] = dict(ENTRY)
            raise RuntimeError("boom")
        self.assertFalse(self.path.exists())

    def test_corrupt_lock_is_an_error_and_never_overwritten(self):
        self.path.parent.mkdir()
        for text in CORRUPT:
            self.path.write_text(text)
            with self.subTest(text=text):
                with self.assertRaises(EngkitError):
                    lockfile.read(self.root)
                with self.assertRaises(EngkitError), lockfile.transaction(self.root):
                    pass
                self.assertEqual(self.path.read_text(), text)

    def test_invalid_entries_are_rejected_on_read(self):
        self.path.parent.mkdir()
        for name, change in BAD_ENTRIES:
            text = json.dumps({"lock_version": 1, "skills": {name: {**GOOD, **change}}})
            self.path.write_text(text)
            with self.subTest(name=name, change=change):
                with self.assertRaises(EngkitError):
                    lockfile.read(self.root)
                with self.assertRaises(EngkitError), lockfile.transaction(self.root):
                    pass
                self.assertEqual(self.path.read_text(), text)

    def test_valid_entries_pass_validation(self):
        self.path.parent.mkdir()
        entry = {**GOOD, "ref": "main", "path": "skills", "commit": "c" * 40}
        self.path.write_text(json.dumps({"lock_version": 1, "skills": {"demo": entry}}))
        self.assertEqual(lockfile.read(self.root)["demo"], entry)

    def test_symlinked_lock_file_is_refused(self):
        target = self.tmp / "victim.lock"
        target.write_text("keep")
        (self.root / ".engkit").mkdir()
        os.symlink(target, self.root / ".engkit/skills.lock.json.lock")
        with self.assertRaises(EngkitError), lockfile.transaction(self.root):
            pass
        self.assertEqual(target.read_text(), "keep")

    def test_symlinked_engkit_dir_is_refused(self):
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, self.root / ".engkit")
        with self.assertRaises(EngkitError):
            lockfile.read(self.root)
        with self.assertRaises(EngkitError), lockfile.transaction(self.root):
            pass
        self.assertEqual(os.listdir(elsewhere), [])

    def test_concurrent_transactions_do_not_lose_updates(self):
        def add(index):
            with lockfile.transaction(self.root) as skills:
                skills[f"s{index}"] = dict(ENTRY)

        threads = [threading.Thread(target=add, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        self.assertEqual(len(lockfile.read(self.root)), 8)

    def test_corrupt_lock_blocks_install_without_changes(self):
        toolkit = self.make_toolkit({"demo": skill_text("demo")})
        self.path.parent.mkdir()
        self.path.write_text("garbage")
        before = snapshot(self.root)
        with self.assertRaises(EngkitError):
            installer.install(toolkit, "demo", "claude", project_dir=self.root)
        self.assertEqual(snapshot(self.root), before)
