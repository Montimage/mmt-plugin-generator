# ocip-plugin

Cisco BroadWorks OCI-P (TCP 2208), label `ocip`, id 960: green (32/32 tests, sanitizers clean); capture evaluation PASS
(synthetic capture). See `REPORT.md`; decisions in `request.md`.

## Re-run

In the `mmt-plugin-dev:local` container with this worktree at `/src`
(`docker run -d --name ocip-plugin -v <worktree>:/src -w /src -e UV_PROJECT_ENVIRONMENT=/opt/ocvenv --entrypoint sleep mmt-plugin-dev:local infinity`,
then `docker exec ocip-plugin uv sync --frozen`):

```sh
docker exec ocip-plugin bash /src/ocip-plugin/loop.sh <n> [--sanitize]   # validate, generate, build, test -> runs/run-<n>/
python3 ocip-plugin/inputs/make_tests.py ocip-plugin/project/tests       # rewrites the packet and session tests
docker exec rulegen bash /pg/ocip-plugin/capture/make-capture.sh         # the capture (Scapy, in mmt-rulegen-dev:local)
# evaluation, in mmt-plugin-dev-tshark:local with the worktree at /src:
uv run --frozen python skills/mmt-plugin-generator/scripts/pcap_eval.py --sdk /sdk/mmt --cc gcc \
  --plugin ocip-plugin/project/build/mmtp_ocip.so --label ocip --parent tcp:port=2208 \
  --capture ocip-plugin/capture/capture.pcap --out ocip-plugin/eval --synthetic \
  --decode-as "tcp.port==2208,xml" --expect-filter "tcp.port==2208 && tcp.len>0" --scope-filter "tcp.port==2208"
```

No `--accept` flags (no drift).

## Kept current

`project/` is regenerated with the examples after a generator change or a version bump (`examples/README.md`,
"Regenerating"); `tests/unit/ocip/` checks that its `generated/` and `plugin.lock` are up to date and its tests are
what `inputs/make_tests.py` writes, and, with `MMT_GOLDEN_SDK` (CI's "Generated code" job), builds it and runs its
tests under the sanitizers (#138).

## Resume

Nothing left for the plugin. Open points are outside it: a real OCI-P capture, OCI over SOAP and TLS (see `REPORT.md`).
