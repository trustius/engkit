# Project profiles, stack definitions and technology packs

All of this is optional. The five skills work without engkit and without any
profile. Commands in profiles are **argument arrays that engkit only
renders**. Detection and generation never execute anything.

## Files

| File | Who writes it | Purpose |
|---|---|---|
| `.engkit/project.yaml` | you, or `engkit project define` | Explicit profile (wins over detection) |
| `stacks/<id>.yaml` (anywhere) | you or the `stack-selection` skill | Reusable stack definition; input to `project define` |
| `.engkit/packs/<id>/pack.yaml` | you | Project-local technology pack |
| `.engkit/generated/` | `engkit project generate` | Rendered context (see `regeneration.md`) |

Schemas: `schemas/profile.schema.json`, `schemas/stack.schema.json` and
`schemas/pack.schema.json` are JSON Schema documents for editors. The
validators in `src/engkit/profiles.py` and `packs.py` are authoritative, and
`tests/test_schemas.py` keeps them in sync.

## Profile (`schema_version: 1`)

```yaml
schema_version: 1
project:
  name: sample-project
  mode: existing            # existing | new
  constraints: {deployment: existing-environment}   # free-form; nothing is mandatory
defaults:                   # optional, applied to every component
  conventions: {notes: [Run linters before review.]}
components:
  - id: service             # [a-z0-9-]
    root: services/service  # project-relative, contained
    stack:                  # languages, runtimes, frameworks, datastores, build_tools, package_managers, tools
      languages: [example-lang, {id: other-lang, version: ">=2,<3"}]
    commands:
      test: {argv: [example-tool, test], cwd: services/service, status: documented, source: CONTRIBUTING.md}
    conventions: {references: [docs/testing.md], notes: []}
    packs: [{id: go, version: 1.0.0}]   # id, or id plus exact version
    evidence: [{source: services/service/manifest, field: name, value: service, confidence: confirmed}]
    unresolved: [Datastore unknown.]
overrides:                  # per-component partial overrides (highest precedence)
  service: {conventions: {notes: [Owned by team A.]}}
```

- Command `status` is one of `unknown`, `documented`, `inferred`, `verified` or
  `ambiguous`. A non-empty `argv` is required unless the status is `unknown`
  or `ambiguous`.
- Evidence `confidence` is `confirmed`, `inferred` or `unknown`. Absent
  evidence is never proof that a technology is absent.
- Nothing web-specific is required. Libraries, CLIs, firmware and data
  pipelines are all valid with only `id` and `root`.

### Resolution and merge rules

Precedence, lowest to highest: **detected → `defaults` → explicit component →
`overrides`**.

- Scalars override. Mappings merge recursively. Lists are **replaced**, with
  two declared exceptions: `components` merge by `id`, and `evidence` is a
  union, so conflicting evidence is kept.
- An explicit component whose `root` equals a detected component's root
  absorbs it, even when the ids differ.
- An explicit component that reuses the id of a detected component at a
  different root is a `component-id-conflict` error. Choose another id or
  match the detected root; engkit does not merge data from two directories.
- A stack category left empty (`languages:` with no value) means "not
  specified", so detected values stay. Use `[]` to clear a category.
- Explicit values that contradict detected ones win, and a `contradiction`
  warning is recorded.
- If detection found a package-manager-dependent command but the package
  manager was ambiguous, declaring exactly one `package_managers` entry fills
  in the command and clears the ambiguity.
- `unresolved` is derived again after merging. It lists an unknown stack,
  unknown or ambiguous test commands, ambiguous package managers, and your own
  notes.
- `engkit project inspect --json` shows the resolved profile, the per-field
  `provenance` (`detected`, `defaults`, `explicit` or `override`) and all
  diagnostics.

## Detection (read-only, bounded)

- A breadth-first walk to depth 8, stopping at 5000 directories. Symlinks are
  never followed. Vendored, generated and cache directories are skipped
  (`node_modules`, `vendor`, `target`, `build`, `dist`, `.venv`, `.git`,
  `.engkit`, and so on).
- Every rule comes from packs. A directory that matches a rule with
  `component: true` becomes a component root, so nested roots become separate
  components. The other rules are evaluated at component roots to add stack
  items, commands and evidence.
- Conflicting lockfiles give the warning `ambiguous-package-manager`. The
  package manager is not chosen for you.
- If nothing matches, you get a generic `root` component with the unknown
  stack listed. Use `project define` to describe the stack manually.

## Stack definitions

```yaml
schema_version: 1
kind: stack
id: example-service
description: ...
project: {mode: new, constraints: {...}}
components: [ ...same shape as profile components... ]
```

`engkit stack validate --file <file> --project-dir <root>` checks the schema,
pack references against that project's registry (bundled plus
`<root>/.engkit/packs`) and declared incompatibilities. The stack file's own
directory never becomes the project root.

## Technology packs

```
.engkit/packs/<id>/
  pack.yaml
  references/*.md        # copied into the generated bundle when selected
  fragments/*.md         # string.Template text rendered per component
```

```yaml
schema_version: 1
kind: pack
id: acme-widget            # must equal the directory name
version: 2.1.0             # exact MAJOR.MINOR.PATCH
description: ...
profile_schema: {min: 1, max: 1}
applies_to: {stack: [widgetlang]}       # stack ids this pack "covers" for compatibility
dependencies: [{id: go, version: 1.0.0}] # exact versions only
conflicts: [other-pack]
incompatible_stack: [some-stack-id]
detect:
  - files: [widget.build]   # exact names relative to the candidate dir, no globs
    component: true
    parse: yaml             # json | yaml | toml (toml needs Python 3.11+)
    key: targets.test       # optional dotted key that must exist
    stack: {languages: [widgetlang]}
    commands: {test: {argv: [widgetc, test], status: documented}}   # argv may use {package_manager}
references: [references/conventions.md]
fragments: [fragments/component.md]   # placeholders: component_id, component_root, pack_id, pack_version, project_name
```

Registry rules:

- Packs come from bundled packs (`packs/` in the distribution) plus
  `<project>/.engkit/packs/*`. No install command and no network access are
  involved.
- A **duplicate id is always an error**, even with the same version, and the
  error names both paths. A custom variant must use a distinct id.
- Dependencies resolve transitively by exact version and are ordered
  dependencies-first, ties broken by id. Missing ids, version mismatches,
  cycles and declared conflicts are errors, reported before anything is
  written.
- Invalid packs that the profile does not select are reported by
  `inspect`/`doctor` but do not block generation.
- No executable code, hooks or commands are allowed. Symlinks that escape the
  pack directory are rejected.

Bundled packs (`go`, `rust`, `javascript`, `typescript`→`javascript`, `jvm`)
are **synthetic, representative examples** that demonstrate the contract. They
are not a supported-stack catalog.

## Workflows

**Existing project:**

```bash
engkit project inspect --project-dir .          # read-only report
# optional: write a stack file for what detection missed, then
engkit stack validate --file my-stack.yaml --project-dir .
engkit project define --stack my-stack.yaml --project-dir .   # refuses a different existing profile
engkit project generate --project-dir . --dry-run
engkit project generate --project-dir . --target all
```

**New project:** use the `stack-selection` skill to compare 2–3 options and
write `stacks/<id>.yaml`, then run `stack validate`, `project define` and
`project generate` as above. engkit does not scaffold application code.

**Unknown stack:** detection gives a `root` component with unknowns. Write a
stack file by hand (`project define`). Skills fall back to generic
workflows for anything unresolved.

**Monorepo:** every component root gets `components/<id>.md` with commands
scoped to that root (`cwd`). Skills pick the component whose root is the
deepest directory containing the task's files, and keep commands separate
for work that spans components.
