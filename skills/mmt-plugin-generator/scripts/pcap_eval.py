#!/usr/bin/env python3
"""Evaluate a built plugin on a capture: what it classifies, and what it extracts.

Part of the mmt-plugin-generator skill (``SKILL.md``, Step 6: evaluate on the
capture). It compiles ``pcap_eval.c`` against the SDK, runs the capture
through mmt-dpi twice (the SDK's plugins alone, then with the plugin), and
compares the plugin's packets and values with what the capture holds:

    pcap_eval.py --sdk <prefix> --plugin <project>/build/mmtp_<label>.so \\
        --label <label> --parent <selector> --capture <pcap> --out <dir> \\
        [--field <attribute>=<tshark field> ...] [--accept <key>=<reason> ...] \\
        [--synthetic]

Expected packets. ``--expect-filter`` is a tshark display filter that
selects the frames that carry the protocol; ``--scope-filter`` selects every
frame of its traffic, empty segments included (a plugin over TCP claims its
whole session). By default both come from ``--parent``: ``udp:port=N`` gives
``udp.port == N && udp.length > 8`` and ``udp.port == N`` (both directions:
mmt-dpi classifies the session), ``tcp:...`` the same with ``tcp.len > 0``,
``ethernet:ethertype=N`` ``eth.type == N``, ``ip:proto=N`` ``ip.proto == N``,
``ipv6:proto=N`` ``ipv6.nxt == N``. Without tshark the expected frames come
from ``mmt_plugin.pcap`` (when importable) and the scope is not measured.

Field agreement. Each ``--field attr=tshark.field`` compares, frame by
frame, the plugin's value with tshark's first occurrence of the field
(integers by value, bytes as hex). Use it when tshark has a dissector for
the protocol (``--decode-as`` passes ``-d`` to tshark, e.g.
``udp.port==5684,coap``).

Drift. tshark is the reference tool: every difference from it is a drift,
listed in ``report.json`` (``drift.items``) and, frame by frame, in
``drift.jsonl``. Each ``--field`` attribute that differs in any expected
frame is one drift (its key is the attribute), the expected frames the
plugin does not claim are the drift ``missed`` and the claimed frames
outside the scope the drift ``foreign``. A drift is a defect, and the
verdict FAIL, unless ``--accept <key>=<reason>`` accepts it; the reason is
recorded with it. With tshark, the drift decides and ``--min-recall`` does
not apply. Without tshark there is no reference: the drift is not checked (a
warning), ``--min-recall`` applies to the frames ``mmt_plugin.pcap``
expects, and ``--field`` is exit 3. ``--min-agreement`` and
``--max-foreign`` are accepted and ignored: an accepted drift replaced them.

Writes in ``--out``: ``bin/pcap_eval`` (linked with the SDK's
``libmmt_core.so.<version>``, whose soname ``lib/`` resolves),
``baseline-plugins/`` (links to the SDK's plugins), ``plugins/`` (the same
and a copy of the plugin), ``baseline.json``, ``plugin.json``,
``frames.jsonl``, ``drift.jsonl`` (with tshark), ``report.json`` and
``report.md``. It never writes under
``--sdk``: an SDK plugin with the plugin's file name (an installed copy) is
left out of both runs. Prints one summary line.

Exit codes: 0 PASS, 1 FAIL (the report says why), 2 usage, 3 environment
(no compiler, the runner does not compile, the SDK is not a prefix, the
capture cannot be read).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RUNNER_SRC = HERE / "pcap_eval.c"
OWN_ATTRIBUTE_LIMIT = 4096  # ids from 4096 are mmt-dpi's generic attributes (p_data, stats, ...)
EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_ENV = 0, 1, 2, 3
REFERENCE = "tshark"  # the only reference tool for the drift check
CLASSIFICATION_KEYS = ("missed", "foreign")  # the drift keys that are not attributes
# libmmt_core.so.<major>.<minor>...: group 1 is its soname, libmmt_core.so.<major>.
CORE_VERSIONED = re.compile(r"^(libmmt_core\.so\.[0-9]+)(\.[0-9]+)+$")


class EvalExit(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def default_filters(selector: str) -> tuple[str, str | None]:
    """(expect filter, scope filter) for a parent selector."""
    proto, _, rest = selector.partition(":")
    keys = dict(item.partition("=")[::2] for item in rest.split(",") if item)
    if proto in ("udp", "tcp"):
        port = keys.get("port") or keys.get("dport") or keys.get("sport")
        if port is None:
            raise EvalExit(EXIT_USAGE, f"--parent {selector!r}: give port=N, dport=N or sport=N")
        scope = f"{proto}.port == {int(port, 0)}"
        payload = "udp.length > 8" if proto == "udp" else "tcp.len > 0"
        return f"{scope} && {payload}", scope
    if proto == "ethernet" and "ethertype" in keys:
        flt = f"eth.type == {int(keys['ethertype'], 0):#06x}"
        return flt, flt
    if proto == "ip" and "proto" in keys:
        flt = f"ip.proto == {int(keys['proto'], 0)}"
        return flt, flt
    if proto == "ipv6" and "proto" in keys:
        flt = f"ipv6.nxt == {int(keys['proto'], 0)}"
        return flt, flt
    raise EvalExit(
        EXIT_USAGE,
        f"--parent {selector!r}: no default filter; pass --expect-filter (and --scope-filter)",
    )


def core_library(sdk: Path) -> Path:
    """The SDK's ``libmmt_core`` shared object: the newest regular file
    ``dpi/lib/libmmt_core.so.<version>``, else ``dpi/lib/libmmt_core.so``
    when it resolves. The package's own links point to absolute ``/opt/mmt``
    paths, so they dangle in an extracted prefix, and ``-lmmt_core`` would
    then link ``libmmt_core.a``: a private copy of the core that the SDK's
    plugins cannot resolve their symbols against."""
    lib = sdk / "dpi" / "lib"
    found = [
        p
        for p in (lib.iterdir() if lib.is_dir() else [])
        if CORE_VERSIONED.match(p.name) and p.is_file() and not p.is_symlink()
    ]
    if found:
        return max(
            found, key=lambda p: tuple(int(n) for n in p.name.split(".so.", 1)[1].split("."))
        )
    plain = lib / "libmmt_core.so"
    if plain.is_file():
        return plain
    raise EvalExit(EXIT_ENV, f"--sdk {sdk}: dpi/lib has no libmmt_core shared object")


def runtime_dir(core: Path, out: Path) -> Path:
    """A directory where ``libmmt_core``'s soname resolves to ``core``:
    ``out/lib``, with a link named after the soname."""
    match = CORE_VERSIONED.match(core.name)
    if match is None:
        return core.parent
    lib = out / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    link = lib / match.group(1)
    if not (link.is_symlink() and os.readlink(link) == str(core)):
        link.unlink(missing_ok=True)
        link.symlink_to(core)
    return lib


def compile_runner(sdk: Path, cc: str, out: Path) -> Path:
    binary = out / "bin" / "pcap_eval"
    # The command the binary was built with: another --sdk or --cc rebuilds it.
    stamp = out / "bin" / "pcap_eval.cmd"
    core = core_library(sdk)
    run_path = runtime_dir(core, out)
    cmd = [
        cc, "-O2", "-Wall", "-o", str(binary), str(RUNNER_SRC),
        f"-I{sdk / 'dpi' / 'include'}", str(core),
        f"-Wl,-rpath,{run_path}", "-ldl", "-lpcap",
    ]  # fmt: skip
    if (
        binary.exists()
        and binary.stat().st_mtime >= RUNNER_SRC.stat().st_mtime
        and stamp.is_file()
        and stamp.read_text("utf-8") == json.dumps(cmd)
    ):
        return binary
    if not shutil.which(cc):
        raise EvalExit(EXIT_ENV, f"compiler {cc!r} not found: pass --cc gcc or --cc clang")
    binary.parent.mkdir(parents=True, exist_ok=True)
    stamp.unlink(missing_ok=True)
    done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise EvalExit(
            EXIT_ENV, f"the runner does not compile (is libpcap-dev installed?):\n{done.stderr}"
        )
    stamp.write_text(json.dumps(cmd), "utf-8")
    return binary


def plugins_dir(sdk: Path, plugin: Path, target: Path, *, with_plugin: bool) -> Path:
    """``target``: links to the SDK's plugins and, ``with_plugin``, a copy of
    the plugin. An SDK plugin with the plugin's file name (an installed copy
    of it) is left out: the baseline runs without the plugin, and the copy
    never goes through a link into the SDK's ``plugins/``."""
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for so in sorted((sdk / "plugins").glob("*.so")):
        if so.name != plugin.name:
            (target / so.name).symlink_to(so.resolve())
    if with_plugin:
        shutil.copy2(plugin, target / plugin.name)
    return target


def run_runner(
    binary: Path, capture: Path, label: str, plugins: Path, dump: Path | None
) -> dict[str, Any]:
    env = dict(os.environ, MMT_DPI_PLUGINS_DIR=str(plugins.resolve()))
    cmd = [str(binary), str(capture), label] + ([str(dump)] if dump else [])
    done = subprocess.run(
        cmd, capture_output=True, text=True, env=env, check=False, stdin=subprocess.DEVNULL
    )
    if done.returncode < 0:
        return {"crashed": True, "signal": -done.returncode, "stderr": done.stderr[-2000:]}
    if done.returncode != 0:
        raise EvalExit(EXIT_ENV, f"the runner failed ({done.returncode}): {done.stderr.strip()}")
    result: dict[str, Any] = json.loads(done.stdout)
    result["crashed"] = False
    return result


def tshark_frames(capture: Path, flt: str, decode_as: list[str]) -> set[int]:
    cmd = ["tshark", "-n", "-r", str(capture), "-Y", flt, "-T", "fields", "-e", "frame.number"]
    for d in decode_as:
        cmd[1:1] = ["-d", d]
    done = subprocess.run(
        cmd, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL
    )
    if done.returncode != 0:
        raise EvalExit(EXIT_USAGE, f"tshark rejects the filter {flt!r}: {done.stderr.strip()}")
    return {int(x) for x in done.stdout.split()}


def fallback_frames(capture: Path, selector: str) -> set[int]:
    """Expected frames without tshark: mmt_plugin.pcap's slicing (both directions)."""
    try:
        from mmt_plugin.commands.init import parse_selector  # type: ignore[import-not-found,unused-ignore]
        from mmt_plugin.pcap import parent_of, read_stream, slice_payloads
    except ImportError as exc:
        raise EvalExit(
            EXIT_ENV, "neither tshark nor the mmt_plugin package: cannot count the expected frames"
        ) from exc
    sel = parse_selector(selector)
    both = [("port" if k in ("sport", "dport") else k, v) for k, v in sel.keys]
    parent = parent_of(sel.text, sel.proto, both)
    with capture.open("rb") as f:
        sliced = slice_payloads(read_stream(f).frames(), parent, 10**9)
    return {p.frame for p in sliced.payloads}


def normalize(value: str) -> str:
    text = value.strip()
    try:
        return str(int(text, 0))
    except ValueError:
        pass
    bare = text.replace(":", "").replace(" ", "").lower()
    if bare and len(bare) % 2 == 0 and all(c in "0123456789abcdef" for c in bare):
        return bare
    return text


def tshark_fields(
    capture: Path, fields: dict[str, str], decode_as: list[str]
) -> dict[int, dict[str, str]]:
    cmd = [
        "tshark",
        "-n",
        "-r",
        str(capture),
        "-T",
        "fields",
        "-E",
        "occurrence=f",
        "-e",
        "frame.number",
    ]
    for d in decode_as:
        cmd[1:1] = ["-d", d]
    for f in fields.values():
        cmd += ["-e", f]
    done = subprocess.run(
        cmd, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL
    )
    if done.returncode != 0:
        raise EvalExit(EXIT_USAGE, f"tshark rejects a --field: {done.stderr.strip()}")
    rows: dict[int, dict[str, str]] = {}
    names = list(fields)
    for line in done.stdout.splitlines():
        cells = line.split("\t")
        values = {n: c for n, c in zip(names, cells[1:], strict=False) if c != ""}
        if values:
            rows[int(cells[0])] = values
    return rows


def field_mismatches(
    dump: list[dict[str, Any]],
    reference: dict[int, dict[str, str]],
    fields: dict[str, str],
    expected: set[int],
) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]]]:
    """Per attribute: the expected frames where tshark has the field, and
    every one of them where the plugin's value differs (``plugin`` None:
    the plugin has no value there)."""
    compared: dict[str, int] = {}
    rows: dict[str, list[dict[str, Any]]] = {}
    by_frame = {row["frame"]: row["attributes"] for row in dump}
    for attr in fields:
        compared[attr] = 0
        rows[attr] = []
        for frame in sorted(expected & set(by_frame)):
            ref = reference.get(frame, {}).get(attr)
            if ref is None:
                continue
            compared[attr] += 1
            got = by_frame[frame].get(attr)
            if got is None or normalize(got) != normalize(ref):
                rows[attr].append({"frame": frame, "tshark": ref, "plugin": got})
    return compared, rows


def compare_fields(
    dump: list[dict[str, Any]],
    reference: dict[int, dict[str, str]],
    fields: dict[str, str],
    expected: set[int],
) -> dict[str, Any]:
    compared, rows = field_mismatches(dump, reference, fields, expected)
    return summarize_fields(fields, compared, rows)


def summarize_fields(
    fields: dict[str, str],
    compared: dict[str, int],
    rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """``report.json``'s ``fields``, from what ``field_mismatches`` returns."""
    out: dict[str, Any] = {}
    for attr in fields:
        n, bad = compared[attr], rows[attr]
        matched = n - len(bad)
        out[attr] = {
            "tshark_field": fields[attr],
            "compared": n,
            "matched": matched,
            "missing_in_plugin": sum(1 for r in bad if r["plugin"] is None),
            "agreement": round(matched / n, 4) if n else None,
            "mismatches": bad[:5],
        }
    return out


def parse_accept(items: list[str], fields: dict[str, str]) -> dict[str, str]:
    """``--accept <key>=<reason>``: the key is a ``--field`` attribute,
    ``missed`` or ``foreign``, the reason is not empty, and each key once."""
    accepted: dict[str, str] = {}
    for item in items:
        key, sep, reason = item.partition("=")
        key, reason = key.strip(), reason.strip()
        if not sep or not key or not reason:
            raise EvalExit(EXIT_USAGE, f"--accept {item!r}: write <key>=<reason>, with a reason")
        if key not in fields and key not in CLASSIFICATION_KEYS:
            known = ", ".join([*fields, *CLASSIFICATION_KEYS])
            raise EvalExit(
                EXIT_USAGE, f"--accept {item!r}: {key!r} is not a drift key (one of: {known})"
            )
        if key in accepted:
            raise EvalExit(EXIT_USAGE, f"--accept {key!r} is given twice")
        accepted[key] = reason
    return accepted


def drift_items(
    field_rows: dict[str, list[dict[str, Any]]],
    fields: dict[str, str],
    missed: list[int],
    foreign: list[int] | None,
    accepted: dict[str, str],
) -> list[dict[str, Any]]:
    """Every drift from the reference: one per ``--field`` attribute that
    differs in an expected frame, then ``missed`` and ``foreign``. Each is a
    ``defect`` unless ``accepted`` names it (then ``accepted``, with its
    reason)."""
    items: list[dict[str, Any]] = []

    def add(key: str, kind: str, frames: list[int], **extra: Any) -> None:
        if not frames:
            return
        reason = accepted.get(key)
        items.append(
            {
                "key": key,
                "kind": kind,
                **extra,
                "frames": len(frames),
                "first_frames": frames[:5],
                "status": "accepted" if reason else "defect",
                "reason": reason,
            }
        )

    for attr, rows in field_rows.items():
        add(attr, "field", [r["frame"] for r in rows], tshark_field=fields[attr])
    add("missed", "classification", missed)
    add("foreign", "classification", foreign or [])
    return items


def drift_lines(
    field_rows: dict[str, list[dict[str, Any]]], missed: list[int], foreign: list[int] | None
) -> list[dict[str, Any]]:
    """``drift.jsonl``: one line per frame of each drift, every frame."""
    lines = [{"key": a, **row} for a, rows in field_rows.items() for row in rows]
    lines += [{"key": "missed", "frame": f} for f in missed]
    lines += [{"key": "foreign", "frame": f} for f in foreign or []]
    return lines


def displaced(baseline: dict[str, Any], plugin: dict[str, Any], label: str) -> dict[str, int]:
    """Paths that lost packets once the plugin was loaded, other than ``*.unknown``."""
    lost: dict[str, int] = {}
    after = plugin.get("paths", {})
    for path, n in baseline.get("paths", {}).items():
        drop = n - after.get(path, 0)
        last = path.rsplit(".", 1)[-1]
        if drop > 0 and last != "unknown" and label.upper() not in path.upper():
            lost[path] = drop
    return lost


def drift_problem(d: dict[str, Any], scope_filter: str | None) -> str:
    """The problem of an open drift (a defect)."""
    if d["key"] == "missed":
        what = f"{d['frames']} expected frames are not classified as the plugin's"
    elif d["key"] == "foreign":
        what = f"{d['frames']} claimed frames are outside {scope_filter!r}"
    else:
        what = f"field {d['key']} differs from {d['tshark_field']} in {d['frames']} frames"
    return (
        f"drift {d['key']}: {what} (first: frame {d['first_frames'][0]}):"
        f" fix the plugin, or --accept {d['key']}=<reason>"
    )


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    sdk: Path = args.sdk.resolve()
    if not (sdk / "dpi" / "include" / "mmt_core.h").is_file() or not (sdk / "plugins").is_dir():
        raise EvalExit(
            EXIT_ENV, f"--sdk {sdk}: not an mmt-dpi prefix (dpi/include/mmt_core.h, plugins/)"
        )
    if not args.plugin.is_file():
        raise EvalExit(
            EXIT_USAGE, f"--plugin {args.plugin}: no such file (run mmt-plugin build first)"
        )
    if not args.capture.is_file():
        raise EvalExit(EXIT_USAGE, f"--capture {args.capture}: no such file")
    fields: dict[str, str] = {}
    for item in args.field:
        attr, sep, tsf = item.partition("=")
        if not sep or not attr or not tsf:
            raise EvalExit(EXIT_USAGE, f"--field {item!r}: write <attribute>=<tshark field>")
        if attr in CLASSIFICATION_KEYS:
            raise EvalExit(EXIT_USAGE, f"--field {item!r}: {attr!r} is a drift key, not a field")
        fields[attr] = tsf
    accepted = parse_accept(args.accept, fields)
    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    have_tshark = shutil.which("tshark") is not None
    if fields and not have_tshark:
        raise EvalExit(EXIT_ENV, "--field needs tshark on PATH")

    binary = compile_runner(sdk, args.cc, out)
    plugin_so = args.plugin.resolve()
    installed = (sdk / "plugins" / plugin_so.name).exists()
    base_dir = plugins_dir(sdk, plugin_so, out / "baseline-plugins", with_plugin=False)
    plugins = plugins_dir(sdk, plugin_so, out / "plugins", with_plugin=True)
    baseline = run_runner(binary, args.capture, args.label, base_dir, None)
    dump_path = out / "frames.jsonl"
    plugin = run_runner(binary, args.capture, args.label, plugins, dump_path)
    (out / "baseline.json").write_text(json.dumps(baseline, indent=2) + "\n", "utf-8")
    (out / "plugin.json").write_text(json.dumps(plugin, indent=2) + "\n", "utf-8")
    dump = (
        [json.loads(line) for line in dump_path.read_text("utf-8").splitlines()]
        if dump_path.exists()
        else []
    )
    claimed = {row["frame"] for row in dump}

    expect_filter, scope_filter = args.expect_filter, args.scope_filter
    if expect_filter is None:
        expect_filter, default_scope = default_filters(args.parent)
        scope_filter = scope_filter or default_scope
    if have_tshark:
        expected = tshark_frames(args.capture, expect_filter, args.decode_as)
        scope = tshark_frames(args.capture, scope_filter, args.decode_as) if scope_filter else None
        source = "tshark"
    else:
        expected, scope, source = (
            fallback_frames(args.capture, args.parent),
            None,
            "mmt_plugin.pcap",
        )
        expect_filter, scope_filter = f"payloads under {args.parent} (both directions)", None

    hit = expected & claimed
    missed = sorted(expected - claimed)
    foreign = sorted(claimed - scope) if scope is not None else None
    recall = round(len(hit) / len(expected), 4) if expected else None
    field_report: dict[str, Any] = {}
    field_rows: dict[str, list[dict[str, Any]]] = {}
    if fields:
        reference = tshark_fields(args.capture, fields, args.decode_as)
        compared, field_rows = field_mismatches(dump, reference, fields, expected)
        field_report = summarize_fields(fields, compared, field_rows)
    drifts = drift_items(field_rows, fields, missed, foreign, accepted) if have_tshark else []
    drift_path = out / "drift.jsonl"
    if have_tshark:
        drift_path.write_text(
            "".join(json.dumps(d) + "\n" for d in drift_lines(field_rows, missed, foreign)),
            "utf-8",
        )
    else:
        drift_path.unlink(missing_ok=True)
    own = {n: a for n, a in plugin.get("attributes", {}).items() if a["id"] < OWN_ATTRIBUTE_LIMIT}
    never = sorted(n for n, a in own.items() if a["present"] == 0)
    lost = displaced(baseline, plugin, args.label)
    by_frame = {row["frame"]: row["attributes"] for row in dump}
    own_names = set(own)
    hollow = sorted(f for f in claimed - expected if own_names & set(by_frame.get(f, {})))

    problems: list[str] = []
    warnings: list[str] = []
    if plugin.get("crashed"):
        problems.append(f"mmt-dpi crashed with the plugin (signal {plugin['signal']})")
    elif not plugin.get("registered"):
        problems.append(
            f"the plugin did not register a protocol named {args.label!r}"
            " (load order, MMT_DPI_PLUGINS_DIR)"
        )
    else:
        if not expected:
            problems.append(
                f"the capture has no frame matching {expect_filter!r}: wrong capture or filter"
            )
        elif have_tshark:
            for d in drifts:
                if d["status"] == "defect":
                    problems.append(drift_problem(d, scope_filter))
        elif recall is not None and recall < args.min_recall:
            problems.append(
                f"recall {recall:.2%} < {args.min_recall:.0%}:"
                f" {len(missed)} expected frames not classified"
            )
        for attr, rep in field_report.items():
            if rep["compared"] == 0:
                warnings.append(
                    f"field {attr}: tshark's {rep['tshark_field']} is in no expected frame"
                )
        if have_tshark and scope is None:
            warnings.append("no --scope-filter: the drift foreign is not checked")
        seen = {d["key"] for d in drifts}
        for key in accepted:
            if have_tshark and key not in seen:
                warnings.append(f"--accept {key}: no such drift on this capture")
        if never:
            warnings.append("attributes never extracted on this capture: " + ", ".join(never))
        if hollow:
            warnings.append(
                f"{len(hollow)} claimed frames carry no protocol bytes but report attribute"
                f" values (first: frame {hollow[0]}): check that the plugin does not read"
                " past an empty payload"
            )
        if lost:
            warnings.append(
                "the plugin takes packets mmt-dpi classified before: "
                + ", ".join(f"{p} ({n})" for p, n in lost.items())
            )
    if baseline.get("crashed"):
        warnings.append("mmt-dpi crashed without the plugin too: the SDK or the capture")
    if installed:
        warnings.append(
            f"the SDK's plugins/ holds a {plugin_so.name} (an installed copy?):"
            " left out of both runs"
        )
    if args.synthetic:
        warnings.append(
            "synthetic capture: its bytes come from the spec as read by the drafter,"
            " not from a real implementation"
        )
    if not have_tshark:
        warnings.append(
            "no tshark: expected frames from mmt_plugin.pcap, scope (foreign frames) not measured,"
            " drift against a reference tool not checked"
            + (" (--accept ignored)" if accepted else "")
        )

    return {
        "schema": 1,
        "verdict": "FAIL" if problems else "PASS",
        "problems": problems,
        "warnings": warnings,
        "capture": {
            "path": str(args.capture),
            "sha256": sha256(args.capture),
            "synthetic": args.synthetic,
        },
        "plugin": {"path": str(args.plugin), "sha256": sha256(args.plugin), "label": args.label},
        "parent": args.parent,
        "expected": {
            "source": source,
            "filter": expect_filter,
            "scope_filter": scope_filter,
            "frames": len(expected),
        },
        "frames": plugin.get("frames", baseline.get("frames")),
        "claimed": len(claimed),
        "hit": len(hit),
        "recall": recall,
        "missed_frames": missed[:50],
        "foreign_frames": foreign[:50] if foreign is not None else None,
        "hollow_frames": hollow[:50],
        "fields": field_report,
        "drift": {
            "reference": REFERENCE if have_tshark else None,
            "checked": have_tshark,
            "open": sum(1 for d in drifts if d["status"] == "defect"),
            "accepted": sum(1 for d in drifts if d["status"] == "accepted"),
            "items": drifts,
            "file": drift_path.name if have_tshark else None,
        },
        "attributes": {
            n: {"present": a["present"], "values": a["values"], "other_values": a["other_values"]}
            for n, a in own.items()
        },
        "paths": {
            "baseline": baseline.get("paths", {}),
            "plugin": plugin.get("paths", {}),
            "displaced": lost,
        },
        "thresholds": {"min_recall": args.min_recall},
    }


def table_cell(text: str) -> str:
    """``text`` in one cell of a Markdown table: each line break a space,
    each ``|`` escaped."""
    return " ".join(text.splitlines()).replace("|", "\\|")


def markdown(r: dict[str, Any]) -> str:
    lines = [
        f"# Capture evaluation: {r['plugin']['label']} — {r['verdict']}",
        "",
        f"- Capture: `{r['capture']['path']}` (sha256 `{r['capture']['sha256'][:16]}…`)"
        + (", **synthetic**" if r["capture"]["synthetic"] else ""),
        f"- Plugin: `{r['plugin']['path']}` (sha256 `{r['plugin']['sha256'][:16]}…`)",
        f"- Parent: `{r['parent']}`; expected frames from {r['expected']['source']}:"
        f" `{r['expected']['filter']}`",
        f"- Frames {r['frames']}, expected {r['expected']['frames']}, claimed {r['claimed']}, "
        f"expected and claimed {r['hit']}, recall {r['recall']}",
        "",
    ]
    if r["problems"]:
        lines += ["## Problems", ""] + [f"- {p}" for p in r["problems"]] + [""]
    if r["warnings"]:
        lines += ["## Warnings", ""] + [f"- {w}" for w in r["warnings"]] + [""]
    if r["fields"]:
        lines += [
            "## Fields against tshark",
            "",
            "| Attribute | tshark field | Compared | Matched | Agreement |",
            "|---|---|---:|---:|---:|",
        ]
        for a, f in r["fields"].items():
            lines.append(
                f"| {a} | `{f['tshark_field']}` | {f['compared']} | {f['matched']}"
                f" | {f['agreement']} |"
            )
        lines.append("")
    drift = r.get("drift")
    if drift is not None:
        lines += ["## Drift against tshark", ""]
        if not drift["checked"]:
            lines += ["Not checked: no tshark (the reference tool) on PATH.", ""]
        elif not drift["items"]:
            lines += ["None: the plugin agrees with tshark on every compared frame.", ""]
        else:
            lines += [
                f"{drift['open']} open (defects), {drift['accepted']} accepted;"
                f" every frame in `{drift['file']}`.",
                "",
                "| Key | Kind | Frames | First frames | Status | Reason |",
                "|---|---|---:|---|---|---|",
            ]
            for d in drift["items"]:
                first = ", ".join(map(str, d["first_frames"]))
                lines.append(
                    f"| {d['key']} | {d['kind']} | {d['frames']} | {first}"
                    f" | {d['status']} | {table_cell(d['reason'] or '')} |"
                )
            lines.append("")
    lines += [
        "## Attributes",
        "",
        "| Attribute | Packets | Most frequent values |",
        "|---|---:|---|",
    ]
    for a, info in r["attributes"].items():
        top = ", ".join(
            f"`{v}` x{n}" for v, n in sorted(info["values"].items(), key=lambda kv: -kv[1])[:4]
        )
        lines.append(f"| {a} | {info['present']} | {top} |")
    lines += [
        "",
        "## Protocol paths",
        "",
        "| Path | Without plugin | With plugin |",
        "|---|---:|---:|",
    ]
    paths = sorted(set(r["paths"]["baseline"]) | set(r["paths"]["plugin"]))
    for p in paths:
        lines.append(
            f"| `{p}` | {r['paths']['baseline'].get(p, 0)} | {r['paths']['plugin'].get(p, 0)} |"
        )
    if r["missed_frames"]:
        lines += ["", "Missed frames (first 50): " + ", ".join(map(str, r["missed_frames"]))]
    if r["foreign_frames"]:
        lines += ["", "Foreign frames (first 50): " + ", ".join(map(str, r["foreign_frames"]))]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("--sdk", type=Path, required=True, help="the mmt-dpi prefix (dpi/, plugins/)")
    p.add_argument(
        "--plugin",
        type=Path,
        required=True,
        help="the built plugin, <project>/build/mmtp_<label>.so",
    )
    p.add_argument("--label", required=True, help="the plugin's label")
    p.add_argument("--parent", required=True, help="the parent selector, as given to init")
    p.add_argument("--capture", type=Path, required=True, help="the pcap or pcapng file")
    p.add_argument(
        "--out", type=Path, required=True, help="the directory for the runs and the report"
    )
    p.add_argument("--cc", default="gcc", help="the compiler for the runner (gcc)")
    p.add_argument("--expect-filter", help="tshark filter of the frames that carry the protocol")
    p.add_argument("--scope-filter", help="tshark filter of every frame of the protocol's traffic")
    p.add_argument("--decode-as", action="append", default=[], help="tshark -d rule (repeatable)")
    p.add_argument(
        "--field", action="append", default=[], help="attribute=tshark.field (repeatable)"
    )
    p.add_argument(
        "--accept",
        action="append",
        default=[],
        help="accept a drift: <attribute|missed|foreign>=<reason> (repeatable)",
    )
    p.add_argument(
        "--synthetic", action="store_true", help="the capture was generated, not recorded"
    )
    p.add_argument(
        "--min-recall",
        type=float,
        default=0.95,
        help="without tshark: the expected frames to classify (0.95)",
    )
    p.add_argument(
        "--min-agreement",
        type=float,
        default=1.0,
        help="ignored: replaced by the drift check and --accept",
    )
    p.add_argument(
        "--max-foreign",
        type=float,
        default=0.0,
        help="ignored: replaced by the drift check and --accept",
    )
    args = p.parse_args(argv)
    try:
        report = evaluate(args)
    except EvalExit as exc:
        print(f"pcap_eval: {exc}", file=sys.stderr)
        return exc.code
    (args.out / "report.json").write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    (args.out / "report.md").write_text(markdown(report), "utf-8")
    print(
        f"pcap_eval: {report['verdict']}: {report['hit']}/{report['expected']['frames']}"
        f" expected frames classified, {len(report['problems'])} problems,"
        f" {len(report['warnings'])} warnings, {report['drift']['open']} open drifts;"
        f" {args.out / 'report.md'}"
    )
    return EXIT_PASS if report["verdict"] == "PASS" else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
