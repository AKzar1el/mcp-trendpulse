import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_EXAMPLE_PATH = Path(__file__).resolve().parents[1] / "examples" / "capture_brief_pack_json.py"
_SPEC = importlib.util.spec_from_file_location("capture_brief_pack_json", _EXAMPLE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
capture = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(capture)


def _evidence_bytes(*, incomplete=False):
    document = {
        "schema_version": 1,
        "source": "Google Trends",
        "markets": [{"market": "SI", "keywords": [{"keyword": "\u0161ola\u6f22\u5b57", "latest_index": 75}]}],
    }
    if incomplete:
        document["incomplete"] = True
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def test_capture_preserves_utf8_bytes_and_forces_json(monkeypatch, tmp_path):
    data = _evidence_bytes()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=data)

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    output = tmp_path / "evidence.json"
    status = capture.main(
        ["--output", str(output), "--keyword", "cvet", "--market", "SI"]
    )

    assert status == 0
    assert output.read_bytes() == data
    assert b"\xc5\xa1" in output.read_bytes()
    assert not output.read_bytes().startswith(b"\xef\xbb\xbf")
    command, options = calls[0]
    assert command[:4] == [capture.sys.executable, "-m", "mcp_trendpulse.cli", "brief-pack"]
    assert command[-2:] == ["--format", "json"]
    assert options["stdout"] == subprocess.PIPE
    assert options["check"] is False
    assert options["timeout"] == 180
    assert options["env"]["PYTHONIOENCODING"] == "utf-8"
    assert len(calls) == 1


def test_nonzero_partial_evidence_is_saved_but_failure_propagates(monkeypatch, tmp_path):
    data = _evidence_bytes(incomplete=True)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 7, stdout=data)

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    output = tmp_path / "partial.json"
    status = capture.main(
        [
            "--output", str(output), "--keyword", "one", "--market", "US",
            "--timeframe", "today 5-y", "--allow-partial",
        ]
    )

    assert status == 7
    assert output.read_bytes() == data
    assert calls[0][-3:] == ["--format", "json", "--allow-partial"]
    assert calls[0][-5:-3] == ["--timeframe", "today 5-y"]
    assert len(calls) == 1


def test_real_child_process_preserves_unicode_and_nonzero_json(monkeypatch, tmp_path):
    original_run = subprocess.run
    payload = _evidence_bytes(incomplete=True)
    child_code = "import sys; sys.stdout.write(sys.argv[1]); sys.exit(6)"

    def run_synthetic(command, **kwargs):
        return original_run(
            [sys.executable, "-c", child_code, payload.decode("utf-8")], **kwargs
        )

    monkeypatch.setattr(capture.subprocess, "run", run_synthetic)
    output = tmp_path / "partial-unicode.json"

    assert capture.main(["--output", str(output), "--keyword", "one", "--market", "SI"]) == 6
    assert output.read_bytes() == payload


def test_incomplete_flag_is_nonzero_even_when_child_exits_zero(monkeypatch, tmp_path):
    data = _evidence_bytes(incomplete=True)
    monkeypatch.setattr(
        capture.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=data),
    )
    output = tmp_path / "partial.json"

    assert capture.main(["--output", str(output), "--keyword", "one", "--market", "US"]) == 1
    assert output.read_bytes() == data


def test_existing_destination_does_not_query_provider(monkeypatch, tmp_path):
    output = tmp_path / "evidence.json"
    output.write_bytes(b"preserve me")
    monkeypatch.setattr(
        capture.subprocess, "run", lambda *args, **kwargs: pytest.fail("provider invoked")
    )

    assert capture.main(["--output", str(output), "--keyword", "one", "--market", "US"]) == 2
    assert output.read_bytes() == b"preserve me"


@pytest.mark.parametrize(
    ("data", "returncode", "expected"),
    [
        (b"", 4, 4),
        (b"not-json", 0, 2),
        (b"\xff", 0, 2),
        (b'{"schema_version": 1, "markets": []}', 0, 2),
    ],
)
def test_invalid_or_empty_output_never_creates_evidence(
    monkeypatch, tmp_path, data, returncode, expected
):
    monkeypatch.setattr(
        capture.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, returncode, stdout=data
        ),
    )
    output = tmp_path / "evidence.json"

    assert capture.main(["--output", str(output), "--keyword", "one", "--market", "US"]) == expected
    assert not output.exists()


def test_timeout_does_not_create_evidence_or_retry(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        raise subprocess.TimeoutExpired(command, 180)

    monkeypatch.setattr(capture.subprocess, "run", fake_run)
    output = tmp_path / "evidence.json"

    assert capture.main(["--output", str(output), "--keyword", "one", "--market", "US"]) == 2
    assert not output.exists()
    assert len(calls) == 1


def test_missing_output_directory_fails_before_provider_call(monkeypatch, tmp_path):
    monkeypatch.setattr(
        capture.subprocess, "run", lambda *args, **kwargs: pytest.fail("provider invoked")
    )
    output = tmp_path / "not-created" / "evidence.json"

    assert capture.main(["--output", str(output), "--keyword", "one", "--market", "US"]) == 2
    assert not output.exists()
