# Contributing

Contributions that improve source accuracy, validation, accessibility, security, tests, or
operational clarity are welcome.

## Development setup

Prerequisites:

- Git
- Python 3.12 or later
- Network access for a full data refresh

The project uses only the Python standard library, so there is no dependency-install step. From the
repository root, run:

```bash
python3 -m compileall -q scripts tests
python3 -m unittest discover -s tests
```

Run a full refresh when changing source parsing, scoring, output contracts, overrides, or the
rendered site:

```bash
python3 scripts/build_site.py
```

Success means the command reports its curation mode and writes `countries.json`,
`sanctions.json`, `evidence.json`, and `index.html` under `docs/`.

## Change guidelines

- Keep the deterministic heuristic as the canonical effective-list decision path.
- Treat AI output as advisory; it must not bypass source-evidence or override validation.
- Fail closed when an upstream source cannot be parsed into recognized regimes.
- Preserve `schema_version` compatibility. A breaking payload change requires a major schema
  version and migration notes.
- Do not hand-edit generated files under `docs/`; change the generator and rebuild them.
- Keep manual override notes suitable for a public repository and public website.
- Add or update tests for behavior changes.
- Update the README, security policy, or output documentation when their source of truth changes.
- Never commit credentials, private data, or raw provider error bodies.

## Pull requests

Before opening a pull request:

1. Run the compile and unit-test commands above.
2. Run a full refresh if your change affects generated output.
3. Review the diff for unexpected country-code removals, source loss, sensitive information, and
   unrelated generated churn.
4. Explain the source-of-truth evidence and operational impact in the pull request.

Use a
[Conventional Commit](https://www.conventionalcommits.org/en/v1.0.0/)-style pull request title.
Accepted types are `feat`, `fix`, `perf`, `revert`, `deps`, `docs`, `chore`, `test`, `ci`, and
`refactor`. Examples:

```text
fix: reject malformed override country codes
docs: document feed schema compatibility
```

Scheduled feed updates use the separate `data:` commit type and are generated automatically.

## Source and policy changes

A source-mapping or heuristic change can alter downstream access controls. Include:

- a link to the authoritative upstream source;
- the old and new country-code behavior;
- why the change is country-level rather than entity-, sector-, or region-level;
- test coverage and a rollback or exclusion option.

Do not use a pull request discussion as legal approval. Repository maintainers and downstream
operators remain responsible for obtaining any required policy or legal review.

## Security reports

Follow [`SECURITY.md`](SECURITY.md). Do not disclose a vulnerability or credential in a public
issue or pull request.
