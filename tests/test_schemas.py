import json
import unittest

from engkit import packs, profiles
from tests.helpers import REPO


def load(name):
    return json.loads((REPO / "schemas" / f"{name}.schema.json").read_text())


class SchemaDriftTest(unittest.TestCase):
    """The JSON Schema documents must agree with the authoritative Python validators."""

    def test_profile_schema_matches_validator(self):
        schema = load("profile")
        self.assertEqual(set(schema["properties"]), profiles.PROFILE_KEYS)
        self.assertEqual(schema["properties"]["schema_version"]["const"], profiles.PROFILE_SCHEMA_VERSION)
        comp = schema["$defs"]["component"]["properties"]
        self.assertEqual(set(comp), profiles.COMPONENT_KEYS)
        self.assertEqual(set(comp["stack"]["properties"]), set(profiles.STACK_CATEGORIES))
        self.assertEqual(set(schema["$defs"]["command"]["properties"]), profiles.COMMAND_KEYS)
        self.assertEqual(schema["$defs"]["command"]["properties"]["status"]["enum"], list(profiles.COMMAND_STATUSES))
        self.assertEqual(set(schema["properties"]["project"]["properties"]), profiles.PROJECT_KEYS)

    def test_stack_schema_matches_validator(self):
        self.assertEqual(set(load("stack")["properties"]), profiles.STACK_DEF_KEYS)

    def test_pack_schema_matches_validator(self):
        schema = load("pack")
        self.assertEqual(set(schema["properties"]), packs.PACK_KEYS)
        self.assertEqual(set(schema["properties"]["detect"]["items"]["properties"]), packs.RULE_KEYS)
        self.assertEqual(schema["properties"]["schema_version"]["const"], packs.PACK_SCHEMA_VERSION)
