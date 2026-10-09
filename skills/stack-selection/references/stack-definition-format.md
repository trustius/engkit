# Stack definition format

Load this reference when recording a selected stack. The authoritative definition is the versioned schema shipped with engkit. This reference describes `schema_version: 1`.

## Shape

```yaml
schema_version: 1
kind: stack
id: my-stack              # lower-case letters, digits, hyphens
description: One sentence describing what this stack is for.
project:
  mode: new               # new | existing
  constraints:
    deployment: unknown   # free-form keys describing constraints
components:
  - id: app
    root: app             # relative, contained; no "..", no absolute paths
    stack:
      languages: []       # each item: "<id>" or {id: <id>, version: <constraint>}
      frameworks: []
      datastores: []
      build_tools: []
      package_managers: []
      runtimes: []
    commands:
      test:
        argv: []          # argument array, rendered only, never executed by engkit
        cwd: app
        status: unknown   # unknown | documented | inferred | verified
    conventions:
      references: []
    packs: []             # pack ids or {id, version}; must exist in the local registry
    evidence: []
    unresolved: []
```

Components use the same shape as the project profile. Fields that do not apply (for example runtime or infrastructure for a library) may be empty; web-specific fields are never required.

## Rules

- **Location:** reusable definitions go in `stacks/<id>.yaml`; a project-specific definition may live in the project. The file's directory is not the project root; pass `--project-dir` explicitly.
- **Validation (user-run):** `engkit stack validate --file <file> --project-dir <root>` checks schema, ids, contained roots, duplicates, pack references, version syntax and declared compatibility rules. Unknown compatibility is a warning, not a pass.
- **Versions:** include a version only when verified from official documentation in this session, or confirmed by the user. Otherwise omit it and add an `unresolved` entry such as "Runtime version unverified; confirm from official documentation."
- **Packs:** reference only ids present in bundled packs or `.engkit/packs/<id>/pack.yaml`. A pin is an exact version. Missing packs fail validation; core skills still work without them.
- **Commands:** for a new project, commands are usually `status: unknown` or `inferred` until the project exists and the user runs them.
- **Unresolved:** record every open constraint so the generated context shows what still needs evidence.

## Applying a definition (user-run follow-ups)

1. `engkit stack validate --file stacks/<id>.yaml --project-dir <root>`
2. `engkit project define --stack stacks/<id>.yaml --project-dir <root>` (refuses an existing different profile)
3. `engkit project generate --project-dir <root> --dry-run`, then without `--dry-run` after review

These are suggestions for the user. Listing them does not authorize running them.

## Synthetic example (illustrative only)

A fictional internal command-line tool with a small local datastore. Identifiers are placeholders, not recommendations.

```yaml
schema_version: 1
kind: stack
id: example-cli-tool
description: Single-binary internal command-line tool with embedded local storage.
project:
  mode: new
  constraints: {deployment: developer-workstations, network: offline}
components:
  - id: cli
    root: cli
    stack:
      languages: [example-lang]
      frameworks: []
      datastores: [example-embedded-db]
      build_tools: [example-build]
      package_managers: []
      runtimes: []
    commands:
      test: {argv: [example-build, test], cwd: cli, status: inferred}
    conventions: {references: []}
    packs: []
    evidence: []
    unresolved:
      - Language and datastore versions unverified; confirm from official documentation.
      - Packaging and distribution method not yet chosen.
```
