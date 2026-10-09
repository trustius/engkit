from engkit import detection, packs
from tests import fixtures
from tests.helpers import REPO, TempDirTest, snapshot


class DetectionTest(TempDirTest):
    def detect(self, files, name="project"):
        root = self.make_project(name, files)
        before = snapshot(root)
        result = detection.detect(root, packs.discover(REPO, root))
        self.assertEqual(snapshot(root), before, "detection must be read-only")
        return result

    def comp(self, result, cid):
        return next(c for c in result.components if c["id"] == cid)

    def test_single_stack_fixtures(self):
        cases = [
            (fixtures.JVM_SERVICE, "languages", ["java"], ["mvn", "test"]),
            (fixtures.GO_CLI, "languages", ["go"], ["go", "test", "./..."]),
            (fixtures.RUST_LIB, "languages", ["rust"], ["cargo", "test"]),
            (fixtures.JS_APP, "languages", ["javascript", "typescript"], ["npm", "run", "test"]),
        ]
        for i, (files, cat, expected, test_argv) in enumerate(cases):
            with self.subTest(case=expected):
                result = self.detect(files, f"p{i}")
                self.assertEqual([c["id"] for c in result.components], ["root"])
                comp = result.components[0]
                self.assertEqual(comp["stack"][cat], expected)
                self.assertEqual(comp["commands"]["test"]["argv"], test_argv)
                self.assertEqual(comp["commands"]["test"]["cwd"], ".")
                self.assertTrue(all(e["confidence"] in ("confirmed", "inferred") for e in comp["evidence"]))

    def test_js_documented_command_comes_from_parsed_key(self):
        comp = self.detect(fixtures.JS_APP).components[0]
        self.assertEqual(comp["commands"]["test"]["status"], "documented")
        self.assertEqual(comp["commands"]["test"]["source"], "package.json#scripts.test")
        self.assertEqual(comp["packs"], ["javascript", "typescript"])

    def test_monorepo_components_and_ambiguity(self):
        result = self.detect(fixtures.MONOREPO)
        self.assertEqual(sorted(c["id"] for c in result.components), ["apps-web", "libs-core", "services-api", "tools-cli"])
        self.assertEqual(self.comp(result, "tools-cli")["commands"]["test"]["cwd"], "tools/cli")
        self.assertEqual(self.comp(result, "services-api")["commands"]["test"]["argv"], ["mvn", "test"])
        web = self.comp(result, "apps-web")
        self.assertEqual(web["stack"]["package_managers"], ["npm", "pnpm"])
        self.assertEqual(web["commands"]["test"], {"argv": [], "cwd": "apps/web", "status": "ambiguous",
                                                   "source": "apps/web/package.json#scripts.test"})
        self.assertIn("ambiguous-package-manager", {d.code for d in result.diagnostics})
        self.assertNotIn("apps/web/node_modules/dep/package.json", result.inputs, "vendored dirs are skipped")
        self.assertFalse((self.tmp / "project" / "scripts" / "EXECUTED_MARKER").exists())

    def test_unknown_stack_fallback(self):
        result = self.detect(fixtures.UNKNOWN)
        self.assertEqual(len(result.components), 1)
        comp = result.components[0]
        self.assertEqual((comp["id"], comp["root"]), ("root", "."))
        self.assertTrue(comp["unresolved"])
        self.assertIn("unknown-stack", {d.code for d in result.diagnostics})

    def test_custom_pack_detection(self):
        files = {**fixtures.custom_pack_files(), "widget.build": "targets:\n  test: [checks]\n"}
        comp = self.detect(files).components[0]
        self.assertEqual(comp["stack"]["languages"], ["widgetlang"])
        self.assertEqual(comp["commands"]["test"]["argv"], ["widgetc", "test"])
        self.assertEqual(comp["packs"], ["acme-widget"])

    def test_symlinked_directories_not_followed(self):
        outside = self.make_project("outside", fixtures.GO_CLI)
        root = self.make_project("proj", fixtures.UNKNOWN)
        (root / "linked").symlink_to(outside)
        result = detection.detect(root, packs.discover(REPO, root))
        self.assertEqual([c["id"] for c in result.components], ["root"])
        self.assertEqual(result.inputs, {})

    def test_malformed_manifest_is_diagnosed_not_fatal(self):
        result = self.detect({"package.json": "{not json"})
        self.assertIn("parse-error", {d.code for d in result.diagnostics})
        self.assertEqual(result.components[0]["id"], "root")

    def test_deeply_nested_manifest_is_diagnosed_not_fatal(self):
        result = self.detect({"package.json": "[" * 100000}, "deep")
        self.assertIn("parse-error", {d.code for d in result.diagnostics})

    def test_non_json_native_parsed_value_is_rendered(self):
        files = {**fixtures.custom_pack_files(), "widget.build": "targets:\n  test: 2020-01-01\n",
                 "tools/cli/go.mod": "module example.test/cli\n"}
        result = self.detect(files, "dated")
        values = [e["value"] for c in result.components for e in c["evidence"] if e.get("field") == "targets.test"]
        self.assertEqual(values, ["\"2020-01-01\""])
