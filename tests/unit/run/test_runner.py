"""``mmt_plugin.capture.runner``: the runner's source, its records, its
report, and ``run`` with a fake runner (``fakes.py``): the stream, the
plugin directory, link types, a capture broken in the middle, a setup
error, a crash, a timeout, the stderr tail, and the memory of the stream."""

from __future__ import annotations

import json
import re
import tracemalloc
from collections.abc import Iterator
from pathlib import Path

import pytest

from mmt_plugin.capture import runner
from mmt_plugin.pcap.reader import Frame, PcapError, read
from mmt_plugin.sdk.resolve import resolve_profile

from . import fakes

samples = fakes.SAMPLES


@pytest.fixture
def fake(tmp_path: Path) -> Path:
    return fakes.fake_runner(tmp_path / "bin")


@pytest.fixture
def plugins(tmp_path: Path) -> dict[str, Path]:
    sdk = tmp_path / "sdk-plugins"
    sdk.mkdir()
    out = {}
    for name in ("libmmt_tcpip.so", "mmtp_fakeproto.so"):
        (sdk / name).write_text("fake\n")
        out[name] = sdk / name
    return out


def _dns(n: int, size: int = 0) -> bytes:
    frame: bytes = samples.udp4(40000 + n, 53, bytes(8 + size))
    return frame


def _frames(datas: list[bytes], linktype: int = samples.ETHERNET) -> list[Frame]:
    return [
        Frame(i + 1, linktype, d, len(d), (1700000000 + i) * 10**9 + 5000)
        for i, d in enumerate(datas)
    ]


def test_the_source_names_every_data_type_of_the_profile() -> None:
    profile = resolve_profile("1.10.2", {}, None, None).profile
    source = runner.runner_source(profile)
    assert "{{" not in source and "{%" not in source
    assert '{MMT_U8_DATA, "MMT_U8_DATA"}' in source
    assert "SDK profile 1.10.2" in source
    assert re.search(r"get_attribute_extracted_data\(", source)
    # Nothing attaches a protocol: the plugin's own parent must find it.
    assert "register_classification_function" not in source


def test_a_record_is_the_lengths_the_time_stamp_and_the_bytes() -> None:
    frame = Frame(1, 1, b"abc", 70, 1_700_000_000_123_456_789)
    data = runner.record(frame)
    assert data[:4] == (3).to_bytes(4, "little")
    assert data[4:8] == (70).to_bytes(4, "little")
    assert data[8:16] == (1_700_000_000).to_bytes(8, "little")
    assert data[16:20] == (123_456_789).to_bytes(4, "little")
    assert data[20:] == b"abc"


def test_raw_ip_is_dlt_raw_and_other_link_types_are_their_own_number() -> None:
    assert runner.dlt_of(101) == 12
    assert runner.dlt_of(1) == 1
    assert runner.dlt_of(113) == 113


def test_the_report_reads_every_line() -> None:
    report = runner.Report()
    for line in [
        "protocol 0 991 FAKEPROTO",
        "attribute 0 2 MMT_U16_DATA size",
        "unknown 1 nope",
        "ready",
        "progress 65536",
        "frames 70000 3",
        "classified 0 12",
        "count 0 0 7",
        "path 69990 99 178 354 991",
        "path 10 99",
        "paths_other 0",
        "name 99 ethernet",
        "end 70000",
    ]:
        report.feed(line)
    assert report.malformed is None
    assert [(p.name, p.id, p.packets, p.counts) for p in report.protocols] == [
        ("FAKEPROTO", 991, 12, [7]),
        ("nope", None, 0, []),
    ]
    assert report.protocols[0].attributes == [(2, "MMT_U16_DATA", "size")]
    assert (report.ready, report.progress, report.frames, report.unprocessed) == (
        True,
        65536,
        70000,
        3,
    )
    assert report.paths == [(69990, (99, 178, 354, 991)), (10, (99,))]
    assert (report.names, report.end) == ({99: "ethernet"}, 70000)


@pytest.mark.parametrize(
    "line", ["frames x 0", "count 3 0 1", "what is this", "protocol 1 2 X", "path"]
)
def test_the_first_line_it_cannot_read_stops_the_report(line: str) -> None:
    report = runner.Report()
    report.feed(line)
    report.feed("end 1")
    assert report.malformed == line
    assert report.end is None


def test_a_report_keeps_at_most_the_runners_paths() -> None:
    report = runner.Report()
    for n in range(runner.MAX_PATHS + 1):
        report.feed(f"path 1 {n}")
    assert len(report.paths) == runner.MAX_PATHS
    assert report.malformed == f"path 1 {runner.MAX_PATHS}"


def test_the_frames_stream_to_the_runner_with_their_time_stamps(
    fake: Path, plugins: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "log"
    monkeypatch.setenv("FAKE_RUNNER_LOG", str(log))
    monkeypatch.setenv("LD_PRELOAD", "/nonexistent.so")
    datas = [_dns(1, 40), _dns(2), samples.udp4(1, 9999, b"x")]
    seen: list[int] = []
    done = runner.run(fake, _frames(datas), plugins, ["991", "udp"], on_frames=seen.append)
    assert done.crash_reason() is None
    assert (done.sent, done.other_linktype, done.dlt, done.linktype) == (3, 0, 1, 1)
    assert seen == [3]
    entry = json.loads(log.read_text())
    assert entry["argv"] == ["1", "991", "udp"]
    assert entry["plugins"] == ["libmmt_tcpip.so", "mmtp_fakeproto.so"]
    assert entry["cwd"] == []  # an empty directory: mmt-dpi also loads ./plugins
    assert entry["frames"] == [[len(d), len(d), 1700000000 + i, 5000] for i, d in enumerate(datas)]
    report = done.report
    assert report.protocols[0].packets == 2
    assert report.protocols[0].counts == [1, 2]
    assert report.protocols[1].name == "udp" and report.protocols[1].id == 354
    assert sorted(report.paths) == [(1, (99, 178, 354, 0)), (2, (99, 178, 354, 991))]


def test_frames_of_another_link_type_than_the_first_are_not_sent(
    fake: Path, plugins: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "log"
    monkeypatch.setenv("FAKE_RUNNER_LOG", str(log))
    frames = _frames([_dns(1), _dns(2)], linktype=101) + _frames([_dns(3)])
    done = runner.run(fake, frames, plugins, ["991"])
    assert (done.sent, done.other_linktype, done.dlt, done.linktype) == (2, 1, 12, 101)
    assert json.loads(log.read_text())["argv"][0] == "12"


def test_no_frame_still_runs_the_runner_with_ethernet(
    fake: Path, plugins: dict[str, Path]
) -> None:
    done = runner.run(fake, [], plugins, ["991"])
    assert done.crash_reason() is None
    assert (done.sent, done.dlt, done.linktype, done.report.frames) == (0, 1, None, 0)


def test_a_capture_broken_in_the_middle_stops_at_the_last_whole_record(
    fake: Path, plugins: dict[str, Path]
) -> None:
    data = samples.pcap([_dns(1), _dns(2), _dns(3)])
    capture = read(data[:-5])
    done = runner.run(fake, capture.frames(), plugins, ["991"], errors=(PcapError,))
    assert isinstance(done.capture_error, PcapError)
    assert done.crash_reason() is None
    assert done.sent == 2 and done.report.frames == 2


def test_a_broken_first_record_is_a_capture_error_too(
    fake: Path, plugins: dict[str, Path]
) -> None:
    data = samples.pcap([_dns(1)])
    done = runner.run(fake, read(data[:-5]).frames(), plugins, ["991"], errors=(PcapError,))
    assert isinstance(done.capture_error, PcapError)
    assert done.sent == 0 and done.report.frames == 0


def test_an_error_it_is_not_told_to_catch_propagates(fake: Path, plugins: dict[str, Path]) -> None:
    def frames() -> Iterator[Frame]:
        yield from _frames([_dns(1)])
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        runner.run(fake, frames(), plugins, ["991"], errors=(PcapError,))


def test_a_setup_error_is_reported_not_a_crash(
    fake: Path, plugins: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RUNNER_ERROR", "the plugin did not register its protocol")
    done = runner.run(fake, _frames([_dns(n) for n in range(50)]), plugins, ["991"])
    assert done.returncode == runner.SETUP_EXIT
    assert done.report.error == "the plugin did not register its protocol"
    assert done.crash_reason() is None
    assert not done.report.ready


def test_a_crash_names_its_frame(
    fake: Path, plugins: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RUNNER_CRASH", "6")
    done = runner.run(fake, _frames([_dns(n) for n in range(10)]), plugins, ["991"])
    assert done.crash_reason() == "killed by SIGSEGV"
    assert done.report.crash == 6
    assert done.report.progress == 4


def test_a_runner_that_exits_before_its_end_line_crashed(
    fake: Path, plugins: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RUNNER_NOEND", "1")
    done = runner.run(fake, _frames([_dns(1)]), plugins, ["991"])
    assert done.crash_reason() == "the runner exited before the end (exit status 0)"


def test_a_timeout_kills_the_runner(
    fake: Path, plugins: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RUNNER_SLEEP", "30")
    done = runner.run(fake, _frames([_dns(1)]), plugins, ["991"], timeout=0.5)
    assert done.timed_out
    assert done.crash_reason() == "timed out"


def test_stderr_keeps_its_last_lines_and_echo_sees_each_one(
    fake: Path, plugins: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_RUNNER_STDERR", "1")
    echoed: list[str] = []
    done = runner.run(
        fake, _frames([_dns(n) for n in range(30)]), plugins, ["991"], echo=echoed.append
    )
    assert len(echoed) == 30
    lines = done.stderr.splitlines()
    assert len(lines) == runner.STDERR_TAIL
    assert lines[-1] == "plugin says frame 30"
    assert done.crash_reason() is None


def test_streaming_a_capture_takes_the_same_memory_whatever_its_size(
    fake: Path, plugins: dict[str, Path]
) -> None:
    """The frames are generated one at a time, as the reader yields them:
    the stream holds one batch, never the capture."""
    payload = bytes(1400)

    def frames(n: int) -> Iterator[Frame]:
        for i in range(n):
            data = samples.udp4(40000 + i % 1000, 53, payload)
            yield Frame(i + 1, samples.ETHERNET, data, len(data), i * 10**6)

    peaks = []
    for n in (2_000, 40_000):  # about 3 MB and 58 MB of frames
        tracemalloc.start()
        try:
            done = runner.run(fake, frames(n), plugins, ["991"])
            peaks.append(tracemalloc.get_traced_memory()[1])
        finally:
            tracemalloc.stop()
        assert done.crash_reason() is None and done.report.frames == n
    assert peaks[1] < 4 * runner.BATCH
    assert peaks[1] < peaks[0] + runner.BATCH
