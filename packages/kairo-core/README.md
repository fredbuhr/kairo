# @kairo/core

Small V0 domain core for KAIRO.

The package deliberately has no runtime dependencies. It writes important entities as human-readable Markdown with stable IDs and explicit metadata. It is not intended to be the final high-scale storage layer; it exists to prove KAIRO's domain contract before introducing a database.

## Implemented V0 records

- projects, including optional parent projects;
- ideas;
- decisions;
- tasks with owner and authority ceiling;
- knowledge claims with epistemic status;
- sources.

## Storage layout

```text
<dataDir>/
  projects/
    ztikix/
      project.md
      ideas/
        idea_<uuid>.md
      decisions/
        decision_<uuid>.md
      tasks/
        task_<uuid>.md
      knowledge/
        claim_<uuid>.md
      sources/
        source_<uuid>.md
```

The live `dataDir` is runtime-private and must not be committed.

## Test

```bash
cd packages/kairo-core
npm test
```

The tests use Node's built-in test runner and a temporary data directory.
