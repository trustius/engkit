# Go testing notes (optional pack reference)

- Tests live next to code in `*_test.go` files; table-driven tests are common.
- `go test ./...` is the conventional command, but confirm against the project's
  own documentation or CI configuration before treating it as authoritative.
- Use `-run <regexp>` to target a single test and `-race` when investigating
  concurrency defects.
