# Rust testing notes (optional pack reference)

- Unit tests usually sit in `#[cfg(test)]` modules; integration tests in `tests/`.
- `cargo test` is conventional; workspaces may need `-p <crate>` to scope a run.
- Doc tests run as part of `cargo test` for library crates.
