"""``mmt-plugin test`` against a real mmt-dpi SDK (plan T2.4: "green on every
corpus model, plus a deliberately broken model that must fail").

Every corpus model that generates is tested in its own project, with its
scaffold ``src/<label>_impl.c``, on its corpus packets
(``tests/corpus/models/<name>/packets/``), with ``--sanitize`` (ASan and
UBSan, 100 truncated and random packets per test): all pass. Then a model
whose offset is wrong fails with the attribute, the expected and the actual
value; user code that reads past the packet passes the plain run but crashes
under the sanitizers, the same crashes for the same seed; a plugin that does
not load is reported; and ``--bench`` measures the plugin and the baseline.

The SDK is an extracted mmt-dpi package, a private prefix (never
``/opt/mmt``), as for ``tests/unit/build/test_sdk.py``::

    MMT_GOLDEN_SDK=<dir>/opt/mmt MMT_GOLDEN_CC=gcc uv run pytest tests/unit/packettest/test_sdk.py

Without ``MMT_GOLDEN_SDK`` the tests skip, unless
``MMT_REQUIRE_GOLDEN_COMPILE=1`` (CI's "Generated code" job) makes them fail.
"""

from __future__ import annotations

import json
import os
import shutil
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from mmt_plugin.cli import main
from mmt_plugin.codegen import Generation, scaffold
from mmt_plugin.commands.generate import make_generation
from mmt_plugin.sdk.detect import read_version
from mmt_plugin.sdk.resolve import ProfileChoice, resolve_profile

SDK_ENV = "MMT_GOLDEN_SDK"
CC_ENV = "MMT_GOLDEN_CC"
REQUIRE_ENV = "MMT_REQUIRE_GOLDEN_COMPILE"
CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "models"


def _skip_or_fail(why: str) -> None:
    if os.environ.get(REQUIRE_ENV) == "1":
        pytest.fail(f"{REQUIRE_ENV}=1 but {why}")
    pytest.skip(why)


def _sdk() -> Path:
    prefix = os.environ.get(SDK_ENV, "")
    if not prefix:
        _skip_or_fail(f"{SDK_ENV} is not set (an extracted mmt-dpi prefix)")
    return Path(prefix)


def _cc() -> str:
    cc = os.environ.get(CC_ENV, "gcc")
    if shutil.which(cc) is None:
        _skip_or_fail(f"{cc} is not installed")
    return cc


@cache
def _choice(version: str) -> ProfileChoice:
    return resolve_profile(version, {}, None, None)


def _version() -> str:
    version = read_version(str(_sdk()))
    assert version is not None, f"{_sdk()} has no VERSION in mmt_core.h"
    return version


def _generation(name: str, version: str) -> Generation | None:
    data = (CORPUS / name / "model.pdl").read_bytes()
    generation, _, _ = make_generation("model.pdl", data, _choice(version))
    return generation


def _accepted() -> list[str]:
    # The SDK is not known at collection time: the list uses the newest
    # profile, and each test checks its model with the SDK's own.
    choice = resolve_profile(None, {}, None, None)
    models = sorted(d.name for d in CORPUS.iterdir() if (d / "model.pdl").is_file())
    return [m for m in models if _generation(m, choice.profile.version) is not None]


ACCEPTED = _accepted()


def _project(name: str, root: Path) -> Path:
    """A project for corpus model ``name``: ``model.pdl``, the scaffold and
    the corpus packets in ``tests/``."""
    generation = _generation(name, _version())
    assert generation is not None, f"{name} does not generate with {_version()}"
    project = root / name
    (project / "src").mkdir(parents=True)
    shutil.copy(CORPUS / name / "model.pdl", project / "model.pdl")
    shutil.copytree(CORPUS / name / "packets", project / "tests")
    impl = scaffold(generation, _choice(_version()).profile)
    (project / impl.path).write_text(impl.text)
    return project


def _test(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *args: str,
) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(project)
    # The host's own plugin directory must never be loaded: the harness sets
    # MMT_DPI_PLUGINS_DIR itself, whatever the environment says.
    monkeypatch.setenv("MMT_DPI_PLUGINS_DIR", str(project / "no-such-plugins"))
    argv = ["--json", "test", "--model", "model.pdl", "--sdk", str(_sdk()), "--cc", _cc()]
    code = main([*argv, *args])
    doc: dict[str, Any] = json.loads(capsys.readouterr().out)
    return code, doc


def _stages(doc: dict[str, Any]) -> dict[str, str]:
    return {s["name"]: s["status"] for s in doc["result"]["stages"]}


def test_the_corpus_has_the_models_generate_accepts() -> None:
    # tests/unit/generate/test_golden.py: 16 corpus models generate.
    assert len(ACCEPTED) == 16


@pytest.mark.parametrize("name", ACCEPTED)
def test_every_corpus_model_passes_its_packet_tests_under_the_sanitizers(
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _project(name, tmp_path)
    code, doc = _test(project, monkeypatch, capsys, "--sanitize", "--fuzz-count", "100")
    assert code == 0, (doc["error"], doc["result"] and doc["result"]["packets"])
    result = doc["result"]
    packets = sorted((CORPUS / name / "packets").glob("*.yaml"))
    assert result["summary"] == {
        "total": len(packets),
        "passed": len(packets),
        "failed": 0,
        "skipped": 0,
    }
    assert all(p["attributes"] > 0 for p in result["packets"]), result["packets"]
    assert result["sanitize"] == {
        "seed": 0,
        "count": 101 * len(packets),
        "crashes": [],
    }
    assert _stages(doc) == {
        "build": "ran",
        "harness": "ran",
        "packets": "ran",
        "sanitize": "ran",
        "bench": "skipped",
    }


def test_a_deliberately_broken_model_fails_with_the_attribute_and_both_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # s_packet_upper reads byte 2 (0x12 = 18) instead of byte 0 (0x0a = 10).
    project = _project("pdl_scopes", tmp_path)
    model = project / "model.pdl"
    text = model.read_text()
    broken = text.replace(
        'alias="s_packet_upper" data_type="MMT_U8_DATA" data_len="sizeof(char)" offset="0"',
        'alias="s_packet_upper" data_type="MMT_U8_DATA" data_len="sizeof(char)" offset="2"',
    )
    assert broken != text
    model.write_text(broken)
    code, doc = _test(project, monkeypatch, capsys)
    assert code == 6
    assert doc["error"]["code"] == "test.packet-failed"
    (packet,) = doc["result"]["packets"]
    assert packet["status"] == "fail"
    assert packet["failures"] == [
        {"attribute": "s_packet_upper", "expected": "10", "actual": "18"}
    ]


def test_user_code_that_reads_past_the_packet_crashes_under_the_sanitizers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project("pdl_scopes", tmp_path)
    impl = project / "src" / "pdl_scopes_impl.c"
    text = impl.read_text()
    hook = "int pdl_scopes_hook_extract_no_off("
    start = text.index(hook)
    end = text.index("\n}\n", start) + 3
    impl.write_text(
        text[:start] + "int pdl_scopes_hook_extract_no_off(const ipacket_t *packet,"
        " mmt_proto_index_t proto_index, attribute_t *extracted_data)\n{\n"
        "    (void)proto_index;\n    (void)extracted_data;\n"
        "    return packet->data[packet->p_hdr->caplen + 3] == 0x42;\n}\n" + text[end:]
    )
    code, doc = _test(project, monkeypatch, capsys, "--sanitize", "--fuzz-count", "20")
    assert code == 6
    assert doc["error"]["code"] == "test.crash"
    sanitize = doc["result"]["sanitize"]
    assert sanitize["crashes"], sanitize
    first = sanitize["crashes"][0]
    assert first["test"] == "pdl_scopes/single-packet-session" and first["index"] == 0
    assert first["reason"] == "AddressSanitizer: heap-buffer-overflow"
    # The same seed, the same crashes.
    assert (
        _test(project, monkeypatch, capsys, "--sanitize", "--fuzz-count", "20")[1]["result"][
            "sanitize"
        ]
        == sanitize
    )


def test_user_code_that_exits_is_a_crash_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project("pdl_scopes", tmp_path)
    impl = project / "src" / "pdl_scopes_impl.c"
    text = impl.read_text()
    start = text.index("int pdl_scopes_hook_extract_no_off(")
    body = text.index("    return 0;\n}\n", start)
    impl.write_text("#include <stdlib.h>\n" + text[:body] + "    exit(0);\n" + text[body:])
    code, doc = _test(project, monkeypatch, capsys)
    assert code == 6 and doc["error"]["code"] == "test.crash", doc["error"]
    (packet,) = doc["result"]["packets"]
    assert packet["status"] == "crash"


@pytest.mark.parametrize(
    ("statement", "args"),
    [
        (r'printf("attr len=%d\n", 3);', ()),
        (r'printf("next hop\ndone\npacket 7\nend 1\n");', ()),
        (r'printf("at offset %d\n", 4);', ("--sanitize", "--fuzz-count", "5")),
        (r'printf("sample x y\n");', ("--bench",)),
    ],
)
def test_user_code_that_prints_harness_like_lines_still_passes(
    statement: str,
    args: tuple[str, ...],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The harness's lines have a stream of their own: the plugin's stdout
    # goes to stderr and is never read as one of them.
    project = _project("pdl_scopes", tmp_path)
    impl = project / "src" / "pdl_scopes_impl.c"
    text = impl.read_text()
    start = text.index("int pdl_scopes_hook_extract_no_off(")
    body = text.index("    return 0;\n}\n", start)
    impl.write_text(f"#include <stdio.h>\n{text[:body]}    {statement}\n{text[body:]}")
    code, doc = _test(project, monkeypatch, capsys, *args)
    assert code == 0, doc["error"]
    (packet,) = doc["result"]["packets"]
    assert packet["status"] == "pass"


def test_ld_library_path_does_not_change_the_sdk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A decoy libmmt_core first on LD_LIBRARY_PATH: the harness must not load it.
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "libmmt_core.so.1").write_bytes(b"not a library")
    monkeypatch.setenv("LD_LIBRARY_PATH", str(decoy))
    project = _project("pdl_bitfields", tmp_path)
    code, doc = _test(project, monkeypatch, capsys)
    assert code == 0, doc["error"]


def test_a_plugin_that_does_not_load_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project("pdl_bitfields", tmp_path)
    impl = project / "src" / "pdl_bitfields_impl.c"
    text = impl.read_text()
    start = text.index("int pdl_bitfields_hook_register_parents(")
    end = text.index("    return 1;\n}\n", start)
    impl.write_text(text[:end] + "    return 0;\n}\n" + text[end + len("    return 1;\n}\n") :])
    code, doc = _test(project, monkeypatch, capsys)
    assert code == 6
    assert doc["error"]["code"] == "test.load-failed", doc["error"]
    assert "init_extraction()" in doc["error"]["message"]


def test_bench_measures_the_plugin_and_the_empty_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = _project("pdl_sized_types", tmp_path)
    code, doc = _test(project, monkeypatch, capsys, "--bench")
    assert code == 0, doc["error"]
    bench = doc["result"]["bench"]
    assert bench["pps"] > 0 and bench["baseline_pps"] > 0 and bench["ratio"] > 0
    assert len(bench["samples"]) == 10
    assert _stages(doc)["bench"] == "ran"
    # A second run: the plugin and the harness are up to date.
    code, doc = _test(project, monkeypatch, capsys)
    assert code == 0
    assert _stages(doc)["build"] == "up-to-date" and _stages(doc)["harness"] == "up-to-date"
