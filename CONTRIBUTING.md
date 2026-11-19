# Contributing

## Pull requests target `dev`

Open every pull request against the `dev` branch, not `main`:

1. Fork your branch from `origin/dev`.
2. Open the PR with base `dev`.
3. A PR is merged after an independent review and green CI, as a squash merge
   with a hand-written message.

`main` is the stable branch. It only receives `dev` through a release PR.
Urgent fixes to `main` are cherry-picked back to `dev`.

Commit messages and PR bodies must not carry AI co-author trailers or
"Generated with" footers.

## Python package

The Python rewrite (`pyproject.toml`, `src/`, `tests/unit/`) uses
[uv](https://docs.astral.sh/uv/). Set up and check it with:

```
uv sync
uv run ruff check
uv run ruff format --check
uv run mypy
uv run pytest
uv run mmt-plugin --version
```

CI runs the same commands on Python 3.10, 3.12 and 3.14 and fails if
`uv.lock` is out of date.

See `AGENTS.md` for build and test commands, and
`docs/design/workflow-redesign.md` for the full branching policy.
