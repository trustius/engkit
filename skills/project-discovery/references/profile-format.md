# Project profile format

Load this reference when drafting a profile proposal. The authoritative definition is the versioned schema shipped with engkit; if the CLI is available, the user can validate a proposal after review. This reference describes `schema_version: 1`.

## Shape

```yaml
schema_version: 1
project:
  name: sample-project
  mode: existing            # existing | new
  constraints:
    deployment: existing-environment
defaults: {}                # optional project-wide commands, conventions, packs
components:
  - id: service             # lower-case letters, digits, hyphens; unique
    root: services/service  # relative, contained in the project; no "..", no absolute paths
    stack:
      languages: []         # each item: "<id>" or {id: <id>, version: <constraint>}
      frameworks: []
      datastores: []
      build_tools: []
      package_managers: []
      runtimes: []
    commands:
      test:
        argv: []            # argument array, never a shell string
        cwd: services/service
        status: unknown     # unknown | documented | inferred | verified
    conventions:
      references: []
    packs: []               # pack ids or {id, version}
    evidence: []
    unresolved:
      - Test command must be obtained from project documentation.
overrides: {}               # per-component-id partial overrides
```

## Field guidance

- **id / root:** one component per independently built unit. Use the deepest directory that contains the unit's manifest or build root. Nested roots are allowed; files belong to the deepest containing root.
- **stack:** list only what evidence supports. Leave lists empty and add an `unresolved` entry rather than guessing. Include a version only when a file states it; do not invent versions.
- **commands:** take argv from documentation, CI configuration or manifest script entries. `documented` means a project document states it; `inferred` means derived from configuration; `verified` only when the user ran it and shared a successful result. `unknown` with an empty argv is acceptable.
- **packs:** reference only pack ids known to exist in the local registry (bundled or `.engkit/packs/<id>/pack.yaml`). If unsure, list the candidate under `unresolved`.
- **evidence:** one entry per observation.

```yaml
evidence:
  - source: services/service/manifest.example   # relative path
    field: dependencies.example-framework        # key or observed location
    value: example-framework                     # detected value, never a secret
    confidence: confirmed                        # confirmed | inferred | unknown
```

- **unresolved:** plain sentences describing each gap or ambiguity, for example "Two lockfiles present (a.lock, b.lock); package manager not selected."
- **overrides:** partial component settings keyed by component id; used when explicit configuration should win over detection.

## Merge rules (for understanding, not for manual execution)

- Explicit user configuration wins over inferred values; component overrides win over project defaults.
- Scalars override; maps merge recursively; lists are replaced unless the schema declares keyed merging.
- Components merge by id. Conflicting evidence is kept and reported as a diagnostic, not silently resolved.

## Synthetic example (illustrative only)

A fictional repository with a web client and an API:

```yaml
schema_version: 1
project: {name: example-shop, mode: existing, constraints: {deployment: existing-environment}}
components:
  - id: api
    root: services/api
    stack: {languages: [example-lang], frameworks: [], datastores: [], build_tools: [], package_managers: [], runtimes: []}
    commands:
      test: {argv: [example-tool, test], cwd: services/api, status: documented}
    conventions: {references: []}
    packs: []
    evidence:
      - {source: services/api/README.md, field: "Testing section", value: "example-tool test", confidence: confirmed}
    unresolved: [Datastore not identified from configuration.]
  - id: web
    root: apps/web
    stack: {languages: [], frameworks: [], datastores: [], build_tools: [], package_managers: [], runtimes: []}
    commands: {}
    conventions: {references: []}
    packs: []
    evidence: []
    unresolved: [Two lockfiles present; package manager ambiguous.]
overrides: {}
```
