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

See `AGENTS.md` for build and test commands, and
`docs/design/workflow-redesign.md` for the full branching policy.
