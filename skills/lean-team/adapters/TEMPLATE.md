# Adapter: <name> (offloads work to <which plan>)

Read this file only when you are about to use <name>. Tag every fact with the version or date it was observed.

- **Availability:** how to check that it is installed and logged in.
- **Run (headless):** the one command — stdin closed (`< /dev/null`), hard timeout, final message and machine-readable result written to files in the scratchpad, run in the background.
- **Workspace and permissions:** which folder it works in, what it may edit, how to allow read-only check commands; what never to enable without the user's OK (full access, skip-permissions modes).
- **Result:** where the final message, status and token usage are, and how to parse them.
- **Limits:** how to read the remaining quota; fallback threshold; how a quota error looks.
- **Follow-up:** how to resume the same conversation instead of starting a new run.
- **Failure signals:** errors, timeouts, empty results, and runs that report success but did nothing (e.g. silently denied commands).
- **Measured profile:** fixed overhead of a trivial run (tokens, seconds), typical latency of a real task, roles it is good and bad at.
- **Platform notes:** shells, encodings, sandbox quirks.
- **Untrusted output:** review the diff and run the project's check yourself before committing.
