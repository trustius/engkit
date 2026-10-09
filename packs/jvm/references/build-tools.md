# JVM build-tool notes (optional pack reference)

- A wrapper script (`gradlew`, `mvnw`) pins the build-tool version; prefer it
  when the project documents it, but never run it as part of detection.
- Multi-module builds may need a module selector (`-pl`, `:module:test`).
