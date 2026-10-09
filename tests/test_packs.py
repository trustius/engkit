from engkit import packs
from tests.fixtures import CUSTOM_PACK, custom_pack_files
from tests.helpers import REPO, TempDirTest


def write_pack(base, pid, version="1.0.0", deps=(), conflicts=(), extra=""):
    d = base / pid
    d.mkdir(parents=True)
    dep_yaml = "".join(f"\n  - {{id: {i}, version: {v}}}" for i, v in deps) or " []"
    (d / "pack.yaml").write_text(
        f"schema_version: 1\nkind: pack\nid: {pid}\nversion: {version}\ndescription: test pack\n"
        f"profile_schema: {{min: 1, max: 1}}\napplies_to: {{stack: [{pid}]}}\n"
        f"dependencies:{dep_yaml}\nconflicts: {list(conflicts)}\n{extra}")
    return d


class PackRegistryTest(TempDirTest):
    def setUp(self):
        super().setUp()
        self.toolkit = self.make_toolkit()
        self.project = self.make_project()
        self.local = self.project / ".engkit" / "packs"
        self.local.mkdir(parents=True)

    def test_bundled_packs_are_valid(self):
        reg = packs.discover(REPO, None)
        self.assertEqual(sorted(reg.packs), ["go", "javascript", "jvm", "rust", "typescript"])
        self.assertEqual([d for d in reg.diagnostics if d.level == "error"], [])
        self.assertTrue(all(p.origin == "bundled" for p in reg.packs.values()))

    def test_project_pack_discovered_and_resolved_with_dependency(self):
        for rel, text in custom_pack_files("").items():
            p = self.local / "acme-widget" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        reg = packs.discover(self.toolkit, self.project)
        self.assertEqual(reg.packs["acme-widget"].origin, ".engkit/packs/acme-widget")
        res = packs.resolve(reg, [("acme-widget", "2.1.0")])
        self.assertTrue(res.ok, res.diagnostics)
        self.assertEqual([p.id for p in res.packs], ["go", "acme-widget"])

    def test_duplicate_ids_are_errors_naming_both(self):
        write_pack(self.local, "go")
        reg = packs.discover(self.toolkit, self.project)
        dup = [d for d in reg.diagnostics if d.code == "duplicate-pack-id"]
        self.assertEqual(len(dup), 1)
        self.assertIn("bundled:packs/go/pack.yaml", dup[0].message)
        self.assertIn(".engkit/packs/go/pack.yaml", dup[0].message)
        res = packs.resolve(reg, [("go", None)])
        self.assertEqual([d.code for d in res.diagnostics], ["duplicate-pack-id"])
        self.assertTrue(packs.resolve(reg, [("rust", None)]).ok, "unrelated packs remain usable")

    def test_exact_version_mismatch_and_missing(self):
        write_pack(self.local, "needs-old-go", deps=[("go", "0.9.0")])
        write_pack(self.local, "needs-ghost", deps=[("ghost", "1.0.0")])
        reg = packs.discover(self.toolkit, self.project)
        self.assertEqual(packs.resolve(reg, [("go", "1.0.1")]).diagnostics[0].code, "version-mismatch")
        self.assertEqual(packs.resolve(reg, [("needs-old-go", None)]).diagnostics[0].code, "version-mismatch")
        self.assertEqual(packs.resolve(reg, [("needs-ghost", None)]).diagnostics[0].code, "missing-pack")
        self.assertEqual(packs.resolve(reg, [("nope", None)]).diagnostics[0].code, "missing-pack")

    def test_cycle_detected(self):
        write_pack(self.local, "aa", deps=[("bb", "1.0.0")])
        write_pack(self.local, "bb", deps=[("aa", "1.0.0")])
        res = packs.resolve(packs.discover(self.toolkit, self.project), [("aa", None)])
        self.assertEqual([d.code for d in res.diagnostics], ["dependency-cycle"])
        self.assertEqual(res.packs, [])

    def test_conflicts_declared(self):
        write_pack(self.local, "left", conflicts=["right"])
        write_pack(self.local, "right")
        res = packs.resolve(packs.discover(self.toolkit, self.project), [("left", None), ("right", None)])
        self.assertEqual([d.code for d in res.diagnostics], ["pack-conflict"])

    def test_dependency_order_with_id_tiebreak(self):
        write_pack(self.local, "zz-base")
        write_pack(self.local, "aa-top", deps=[("zz-base", "1.0.0"), ("mm-mid", "1.0.0")])
        write_pack(self.local, "mm-mid", deps=[("zz-base", "1.0.0")])
        res = packs.resolve(packs.discover(self.toolkit, self.project), [("aa-top", None), ("go", None)])
        self.assertEqual([p.id for p in res.packs], ["go", "zz-base", "mm-mid", "aa-top"])

    def test_invalid_packs(self):
        cases = {
            "bad-ref": "references: [../../../etc/passwd]\n",
            "missing-ref": "references: [references/none.md]\n",
            "bad-rule": "detect:\n  - files: ['**/*.json']\n",
            "bad-placeholder": "fragments: [frag.md]\n",
            "non-utf8": "fragments: [frag.md]\n",
        }
        for pid, extra in cases.items():
            write_pack(self.local, pid, extra=extra)
        (self.local / "bad-placeholder" / "frag.md").write_text("hello ${secret_env}\n")
        (self.local / "non-utf8" / "frag.md").write_bytes(b"caf\xe9 ${component_id}\n")
        write_pack(self.local, "wrong-schema", extra="").joinpath("pack.yaml").write_text(
            CUSTOM_PACK.replace("id: acme-widget", "id: wrong-schema").replace("{min: 1, max: 1}", "{min: 2, max: 3}"))
        (self.local / "malformed").mkdir()
        (self.local / "malformed" / "pack.yaml").write_text("id: [\n")
        reg = packs.discover(self.toolkit, self.project)
        for pid in list(cases) + ["wrong-schema", "malformed"]:
            with self.subTest(pid=pid):
                self.assertFalse(reg.packs[pid].valid)
                self.assertEqual(packs.resolve(reg, [(pid, None)]).diagnostics[0].code, "invalid-pack")
        self.assertIn("schema-incompatible", {d.code for d in reg.packs["wrong-schema"].errors})
        self.assertIn("invalid-template", {d.code for d in reg.packs["non-utf8"].errors})
        self.assertTrue(packs.resolve(reg, [("go", None)]).ok, "invalid unrelated packs do not block valid ones")

    def test_symlink_escape_rejected(self):
        d = write_pack(self.local, "linky", extra="references: [ref.md]\n")
        outside = self.tmp / "outside.md"
        outside.write_text("x")
        (d / "ref.md").symlink_to(outside)
        reg = packs.discover(self.toolkit, self.project)
        self.assertFalse(reg.packs["linky"].valid)

    def test_template_checker(self):
        allowed = {"a"}
        self.assertIsNone(packs.check_template("x $a ${a} $$5", allowed))
        self.assertIn("unknown placeholders", packs.check_template("${b}", allowed))
        self.assertIn("invalid", packs.check_template("cost $ 5", allowed))
