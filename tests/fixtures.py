"""Synthetic project fixtures (test coverage examples, not supported-stack defaults)."""

JVM_SERVICE = {
    "pom.xml": "<project><artifactId>example-service</artifactId></project>\n",
    "src/main/java/Example.java": "class Example {}\n",
}
GO_CLI = {"go.mod": "module example.test/cli\n\ngo 1.22\n", "main.go": "package main\n"}
RUST_LIB = {"Cargo.toml": "[package]\nname = \"example\"\nversion = \"0.1.0\"\n", "src/lib.rs": "\n"}
JS_APP = {
    "package.json": '{"name": "web", "scripts": {"test": "node --test"}}\n',
    "package-lock.json": "{}\n",
    "tsconfig.json": "{}\n",
}
MONOREPO = {
    "README.md": "# Mixed monorepo (synthetic)\n",
    "services/api/pom.xml": "<project/>\n",
    "tools/cli/go.mod": "module example.test/cli\n",
    "libs/core/Cargo.toml": "[package]\nname = \"core\"\n",
    "apps/web/package.json": '{"scripts": {"test": "node --test", "build": "node build.js"}}\n',
    "apps/web/package-lock.json": "{}\n",
    "apps/web/pnpm-lock.yaml": "lockfileVersion: 9\n",
    "apps/web/node_modules/dep/package.json": '{"name": "ignored"}\n',
    "scripts/bootstrap.sh": "#!/bin/sh\ntouch EXECUTED_MARKER\n",
}
UNKNOWN = {"BUILD.custom": "steps: compile then link\n", "src/main.xyz": "print hello\n"}

CUSTOM_PACK = """schema_version: 1
kind: pack
id: acme-widget
version: 2.1.0
description: Synthetic user-defined pack for a made-up build system.
profile_schema: {min: 1, max: 1}
applies_to:
  stack: [widgetlang, widgetc]
dependencies:
  - {id: go, version: 1.0.0}
detect:
  - files: [widget.build]
    component: true
    parse: yaml
    stack: {languages: [widgetlang], build_tools: [widgetc]}
  - files: [widget.build]
    parse: yaml
    key: targets.test
    commands:
      test: {argv: [widgetc, test], status: documented}
references: [references/conventions.md]
fragments: [fragments/component.md]
"""


def custom_pack_files(prefix: str = ".engkit/packs/acme-widget/") -> dict:
    return {
        prefix + "pack.yaml": CUSTOM_PACK,
        prefix + "references/conventions.md": "# Widget conventions\n\nTests live in `checks/`.\n",
        prefix + "fragments/component.md": "- `${component_id}` uses widget conventions from `${pack_id}`.\n",
    }
