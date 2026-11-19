# Claude Code instructions

The project instructions live in `AGENTS.md`, imported here:

@AGENTS.md

Hard rules, repeated so they cannot be missed:

- Never `sudo`, never write `/opt/mmt`; run checks with
  `MMT_BASE=<private prefix> bash tests/check_ndn_plugin.sh`.
- Fork from `origin/dev`, open PRs against `dev`, never force-push.
- No `Co-Authored-By` trailers and no "Generated with" footers in commits or
  PR bodies.
- Keep existing line endings (`README.md` is CRLF; check with `cat -A`).
