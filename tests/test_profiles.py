import unittest

from engkit import profiles
from engkit.resolution import resolve


def codes(diags):
    return {d.code for d in diags if d.level == "error"}


def profile(**extra):
    data = {"schema_version": 1, "project": {"name": "demo", "mode": "existing"}, "components": []}
    data.update(extra)
    return data


class ProfileValidationTest(unittest.TestCase):
    def test_minimal_profiles_without_web_fields(self):
        for comp in (
            {"id": "lib", "root": "."},
            {"id": "firmware", "root": "fw", "stack": {"languages": ["c"]}, "commands": {"test": {"argv": [], "status": "unknown"}}},
            {"id": "pipeline", "root": "jobs/etl", "unresolved": ["Scheduler unknown."]},
        ):
            with self.subTest(comp=comp["id"]):
                self.assertEqual(profiles.validate_profile(profile(components=[comp])), [])
        self.assertEqual(profiles.validate_profile(profile(project={"name": "new-thing", "mode": "new"})), [])

    def test_schema_versions(self):
        self.assertIn("schema-version", codes(profiles.validate_profile({"project": {"name": "x"}})))
        self.assertIn("schema-version", codes(profiles.validate_profile(profile(schema_version=2))))
        self.assertIn("schema-version", codes(profiles.validate_profile(profile(schema_version="1"))))

    def test_malformed_input(self):
        self.assertIn("type", codes(profiles.validate_profile(["not", "a", "mapping"])))
        _, diags = profiles.parse_yaml("a: [b", "x.yaml")
        self.assertEqual(diags[0].code, "malformed-yaml")
        self.assertIn("unknown-field", codes(profiles.validate_profile(profile(extra=1))))
        bad_cmd = {"id": "a", "root": ".", "commands": {"test": {"argv": "make test"}}}
        self.assertIn("type", codes(profiles.validate_profile(profile(components=[bad_cmd]))))
        verified_empty = {"id": "a", "root": ".", "commands": {"test": {"argv": [], "status": "verified"}}}
        self.assertIn("required", codes(profiles.validate_profile(profile(components=[verified_empty]))))

    def test_contained_paths(self):
        for root in ("../outside", "/abs", "a/../../b", "a//b", "a\\b"):
            with self.subTest(root=root):
                diags = profiles.validate_profile(profile(components=[{"id": "a", "root": root}]))
                self.assertIn("unsafe-path", codes(diags))
        cwd_escape = {"id": "a", "root": ".", "commands": {"t": {"argv": ["x"], "cwd": "../..", "status": "documented"}}}
        self.assertIn("unsafe-path", codes(profiles.validate_profile(profile(components=[cwd_escape]))))

    def test_duplicate_ids_roots_and_entries(self):
        comps = [{"id": "a", "root": "x"}, {"id": "a", "root": "y"}, {"id": "b", "root": "x"}]
        self.assertTrue({"duplicate-id", "duplicate-root"} <= codes(profiles.validate_profile(profile(components=comps))))
        dup_stack = {"id": "a", "root": ".", "stack": {"languages": ["go", "go"]}}
        self.assertIn("duplicate-entry", codes(profiles.validate_profile(profile(components=[dup_stack]))))

    def test_version_syntax(self):
        ok = {"id": "a", "root": ".", "stack": {"languages": [{"id": "go", "version": ">=1.21,<2"}]},
              "packs": [{"id": "go", "version": "1.0.0"}]}
        self.assertEqual(profiles.validate_profile(profile(components=[ok])), [])
        bad = {"id": "a", "root": ".", "stack": {"languages": [{"id": "go", "version": "latest!"}]}}
        self.assertIn("version-syntax", codes(profiles.validate_profile(profile(components=[bad]))))
        loose_pin = {"id": "a", "root": ".", "packs": [{"id": "go", "version": "^1.0"}]}
        self.assertIn("version-syntax", codes(profiles.validate_profile(profile(components=[loose_pin]))))

    def test_stack_definition(self):
        good = {"schema_version": 1, "kind": "stack", "id": "s", "components": [{"id": "a", "root": "."}]}
        self.assertEqual(profiles.validate_stack_definition(good, "s.yaml"), [])
        self.assertIn("required", codes(profiles.validate_stack_definition({**good, "components": []}, "s.yaml")))
        self.assertIn("kind", codes(profiles.validate_stack_definition({**good, "kind": "pack"}, "s.yaml")))


class MergeTest(unittest.TestCase):
    def test_scalar_map_and_list_rules(self):
        base = {"a": 1, "m": {"x": 1, "y": [1, 2]}, "l": [1, 2, 3]}
        out = profiles.merge(base, {"a": 2, "m": {"y": [9]}, "l": [7]})
        self.assertEqual(out, {"a": 2, "m": {"x": 1, "y": [9]}, "l": [7]})
        self.assertEqual(base["l"], [1, 2, 3], "inputs are not mutated")

    def test_keyed_component_merge(self):
        base = {"components": [{"id": "a", "root": "a", "packs": ["x"]}, {"id": "b", "root": "b"}]}
        out = profiles.merge(base, {"components": [{"id": "a", "packs": ["y"]}, {"id": "c", "root": "c"}]})
        self.assertEqual([c["id"] for c in out["components"]], ["a", "b", "c"])
        self.assertEqual(out["components"][0], {"id": "a", "root": "a", "packs": ["y"]})

    def test_evidence_union(self):
        e1, e2 = {"source": "a", "value": "1"}, {"source": "b", "value": "2"}
        self.assertEqual(profiles.merge({"evidence": [e1]}, {"evidence": [e1, e2]})["evidence"], [e1, e2])


class ResolutionTest(unittest.TestCase):
    def detected(self):
        comp = profiles.empty_component("svc", "svc")
        comp["stack"]["languages"] = ["go"]
        comp["commands"]["test"] = {"argv": ["go", "test", "./..."], "cwd": "svc", "status": "inferred", "source": "svc/go.mod"}
        comp["evidence"] = [{"source": "svc/go.mod", "field": None, "value": "present", "confidence": "confirmed"}]
        return {"project": {"name": "demo", "mode": "existing"}, "components": [comp]}

    def test_explicit_wins_and_contradictions_visible(self):
        explicit = profile(components=[{"id": "svc", "root": "svc", "stack": {"languages": ["go", "c"]},
                                        "commands": {"test": {"argv": ["make", "check"], "status": "documented"}}}])
        res = resolve(self.detected(), explicit)
        comp = res.profile["components"][0]
        self.assertEqual(comp["stack"]["languages"], ["go", "c"])
        self.assertEqual(comp["commands"]["test"]["argv"], ["make", "check"])
        self.assertEqual(comp["commands"]["test"]["cwd"], "svc")
        contradictions = [d for d in res.diagnostics if d.code == "contradiction"]
        self.assertEqual(len(contradictions), 2)
        self.assertEqual(res.provenance["svc"]["stack.languages"], "explicit")
        self.assertEqual(comp["evidence"], self.detected()["components"][0]["evidence"])

    def test_precedence_detected_defaults_explicit_override(self):
        explicit = profile(
            defaults={"conventions": {"notes": ["project default"]}, "commands": {"lint": {"argv": ["lint"], "status": "documented"}}},
            components=[{"id": "svc", "root": "svc", "commands": {"lint": {"argv": ["lint", "--strict"], "status": "documented"}}}],
            overrides={"svc": {"conventions": {"notes": ["override"]}}},
        )
        res = resolve(self.detected(), explicit)
        comp = res.profile["components"][0]
        self.assertEqual(comp["commands"]["lint"]["argv"], ["lint", "--strict"])
        self.assertEqual(comp["conventions"]["notes"], ["override"])
        self.assertEqual(res.provenance["svc"]["conventions.notes"], "override")
        self.assertEqual(res.provenance["svc"]["commands.test.argv"], "detected")

    def test_explicit_component_absorbs_detected_root(self):
        res = resolve(self.detected(), profile(components=[{"id": "backend", "root": "svc"}]))
        self.assertEqual([c["id"] for c in res.profile["components"]], ["backend"])
        self.assertEqual(res.profile["components"][0]["stack"]["languages"], ["go"])

    def test_null_stack_category_means_unspecified(self):
        explicit = profile(components=[{"id": "svc", "root": "svc", "stack": {"languages": None, "package_managers": None}}])
        self.assertEqual(profiles.validate_profile(explicit), [])
        res = resolve(self.detected(), explicit)
        comp = res.profile["components"][0]
        self.assertEqual(comp["stack"]["languages"], ["go"])
        self.assertEqual(comp["stack"]["package_managers"], [])

    def test_explicit_id_reused_at_other_root_is_error(self):
        api = profiles.empty_component("api", "api")
        nested = profiles.empty_component("services-api", "services/api")
        detected = {"project": {"name": "demo"}, "components": [api, nested]}
        for comp in ({"id": "api", "root": "services/api"}, {"id": "api", "root": "other/dir"}):
            with self.subTest(root=comp["root"]):
                res = resolve(detected, profile(components=[comp]))
                self.assertIn("component-id-conflict", codes(res.diagnostics))
                self.assertFalse(res.ok)

    def test_unknown_stack_unresolved_listed(self):
        res = resolve({"project": {"name": "x"}, "components": [profiles.empty_component("root", ".")]}, None)
        notes = res.profile["components"][0]["unresolved"]
        self.assertTrue(any("Stack is unknown" in n for n in notes))
        self.assertTrue(any("Test command is unknown" in n for n in notes))
