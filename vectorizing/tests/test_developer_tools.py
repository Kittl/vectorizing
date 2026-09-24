"""Exercise offline reports, failure exits and benchmark measurement contracts."""

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from scripts import _vectorization as shared
from scripts import benchmark_vectorization as bench
from scripts import vectorization_outputs as outputs

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8">'
    '<rect width="8" height="8" fill="red"/></svg>'
)
DETAILS = {
    "input": {
        "image": "1px.jpg",
        "sha256": "fixture",
        "solver": "binary",
        "color_count": None,
    },
    "colors": [[255, 0, 0, 1]],
    "colors_dtype": "int64",
    "dimensions": [8, 8],
    "bounds": {"left": 0, "top": 0, "right": 8, "bottom": 8, "width": 8, "height": 8},
}


@pytest.fixture
def fake_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supply small deterministic outputs without exercising numerical algorithms."""
    monkeypatch.setattr(
        shared,
        "prepare_case",
        lambda *_: lambda: (SVG, copy.deepcopy(DETAILS)),
    )
    monkeypatch.setattr(shared, "environment", lambda: {"python": "fixture"})


def save_capture(folder: Path, *names: str) -> dict[str, object]:
    """Capture fixture outputs through the public command interface."""
    args = ["capture", str(folder)]
    for name in names or ("1px_binary",):
        args += ["--case", name]
    assert outputs.main(args) == 0
    return json.loads((folder / "outputs.json").read_text())


def test_capture_and_compare(tmp_path: Path, fake_solver: None) -> None:
    """Artifacts contain actual SVG/pixel hashes and compare across metadata labels."""
    before, after = tmp_path / "before", tmp_path / "after"
    report = save_capture(before)
    save_capture(after)
    assert (before / "1px_binary.svg").read_bytes() == SVG.encode()
    record = report["cases"]["1px_binary"]
    assert record["rgba_shape"] == [8, 8, 4]
    assert record["rgba_sha256"] == outputs.pixels(before / "1px_binary.png")[0]
    assert record["svg_sha256"] == shared.file_hash(before / "1px_binary.svg")
    report["label"] = "different label"
    report["environment"] = {"python": "other runtime"}
    report["source_sha256"] = "different source"
    (after / "outputs.json").write_text(json.dumps(report))
    assert outputs.main(["compare", str(before), str(after)]) == 0


@pytest.mark.parametrize(
    "field",
    ["colors", "colors_dtype", "dimensions", "bounds", "input"],
)
def test_changed_metadata_fails(
    tmp_path: Path,
    fake_solver: None,
    field: str,
) -> None:
    """Equal rendered pixels cannot hide changed solver metadata or input identity."""
    before, after = tmp_path / "before", tmp_path / "after"
    save_capture(before)
    report = save_capture(after)
    report["cases"]["1px_binary"][field] = "changed"
    (after / "outputs.json").write_text(json.dumps(report))
    assert outputs.main(["compare", str(before), str(after)]) == 1


def test_changed_svg_fails(tmp_path: Path, fake_solver: None) -> None:
    """Different SVG bytes fail even when both versions render identically."""
    before, after = tmp_path / "before", tmp_path / "after"
    save_capture(before)
    report = save_capture(after)
    path = after / "1px_binary.svg"
    path.write_bytes(path.read_bytes() + b"\n")
    report["cases"]["1px_binary"]["svg_sha256"] = shared.file_hash(path)
    (after / "outputs.json").write_text(json.dumps(report))
    assert outputs.main(["compare", str(before), str(after)]) == 1


def test_changed_pixels_fail(tmp_path: Path, fake_solver: None) -> None:
    """Raster differences fail even when the SVG and solver metadata match."""
    before, after = tmp_path / "before", tmp_path / "after"
    save_capture(before)
    report = save_capture(after)
    Image.new("RGBA", (8, 8), "blue").save(after / "1px_binary.png")
    report["cases"]["1px_binary"]["rgba_sha256"] = outputs.pixels(
        after / "1px_binary.png",
    )[0]
    (after / "outputs.json").write_text(json.dumps(report))
    assert outputs.main(["compare", str(before), str(after)]) == 1


def test_changed_case_sets_fail(tmp_path: Path, fake_solver: None) -> None:
    """Neither missing nor extra cases are silently skipped."""
    before, after = tmp_path / "before", tmp_path / "after"
    save_capture(before)
    save_capture(after, "1px_binary", "empty-color")
    assert outputs.main(["compare", str(before), str(after)]) == 1
    assert outputs.main(["compare", str(after), str(before)]) == 1


@pytest.mark.parametrize(
    "damage",
    ["svg", "png", "missing", "empty", "format", "fields", "nan", "name"],
)
def test_invalid_captures_fail(
    tmp_path: Path,
    fake_solver: None,
    damage: str,
) -> None:
    """Corrupted, incomplete and unsupported captures cannot report equality."""
    report = save_capture(tmp_path)
    if damage == "svg":
        (tmp_path / "1px_binary.svg").write_text("changed")
    elif damage == "png":
        Image.new("RGBA", (8, 8), "blue").save(tmp_path / "1px_binary.png")
    elif damage == "missing":
        (tmp_path / "1px_binary.png").unlink()
    elif damage == "empty":
        report["cases"] = {}
    elif damage == "format":
        report["schema_version"] = 100
    elif damage == "fields":
        del report["cases"]["1px_binary"]["bounds"]
    elif damage == "nan":
        report["cases"]["1px_binary"]["bounds"] = float("nan")
    else:
        report["cases"] = {"../escape": report["cases"]["1px_binary"]}
    (tmp_path / "outputs.json").write_text(json.dumps(report))
    with pytest.raises(SystemExit) as error:
        outputs.main(["compare", str(tmp_path), str(tmp_path)])
    assert error.value.code == 2


def test_refuse_overwrites(tmp_path: Path, fake_solver: None) -> None:
    """Existing captures and benchmark reports survive accidental repeated commands."""
    save_capture(tmp_path)
    original = (tmp_path / "outputs.json").read_bytes()
    for command, args in [
        (outputs.main, ["capture", str(tmp_path), "--case", "1px_binary"]),
        (bench.main, ["--output", str(tmp_path / "outputs.json")]),
    ]:
        with pytest.raises(SystemExit) as error:
            command(args)
        assert error.value.code == 2
    assert (tmp_path / "outputs.json").read_bytes() == original


@pytest.mark.parametrize("kind", ["capture", "benchmark"])
def test_racing_writer_cannot_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    """Files created after the initial existence check are also protected."""
    path = tmp_path / ("1px_binary.svg" if kind == "capture" else "report.json")

    def other_capture(*_: object) -> object:
        path.write_text("another writer")
        return lambda: (SVG, DETAILS)

    def other_benchmark(*_: object) -> tuple[dict[str, object], bool]:
        path.write_text("another writer")
        return {}, True

    monkeypatch.setattr(shared, "prepare_case", other_capture)
    monkeypatch.setattr(bench, "benchmark", other_benchmark)
    with pytest.raises(SystemExit) as error:
        if kind == "capture":
            outputs.main(["capture", str(tmp_path), "--case", "1px_binary"])
        else:
            bench.main(["--output", str(path)])
    assert error.value.code == 2
    assert path.read_text() == "another writer"


def test_failed_capture_has_no_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed run cannot leave a manifest advertising a complete baseline."""
    monkeypatch.setattr(shared, "prepare_case", Mock(side_effect=ValueError("failed")))
    with pytest.raises(SystemExit):
        outputs.main(["capture", str(tmp_path), "--case", "1px_binary"])
    assert not (tmp_path / "outputs.json").exists()


@pytest.mark.parametrize("platform,value", [("linux", 3072), ("darwin", 3145728)])
def test_rss_units(monkeypatch: pytest.MonkeyPatch, platform: str, value: int) -> None:
    """Linux KiB and macOS byte counters both become MiB."""
    resource = pytest.importorskip("resource")
    monkeypatch.setattr(bench.sys, "platform", platform)
    monkeypatch.setattr(
        resource,
        "getrusage",
        lambda _: SimpleNamespace(ru_maxrss=value),
    )
    assert bench.peak_rss_mib() == 3


def test_alternation_medians_and_equality(monkeypatch: pytest.MonkeyPatch) -> None:
    """Paired samples alternate order and report medians rather than best runs."""
    order = []
    times = {"baseline": iter([9, 1, 5]), "candidate": iter([3, 1, 2])}

    def measure(name: str, root: Path, warmups: int) -> dict[str, object]:
        order.append(root.name)
        assert name == "bubbles" and warmups == 2
        return {
            "elapsed_ms": next(times[root.name]),
            "peak_rss_mib": 12,
            "output": {"same": True},
            "consistent": True,
        }

    monkeypatch.setattr(bench, "run_sample", measure)
    cases, equal = bench.benchmark(
        ["bubbles"],
        {name: Path(name) for name in times},
        repeats=3,
        warmups=2,
    )
    assert order == [
        "baseline",
        "candidate",
        "candidate",
        "baseline",
        "baseline",
        "candidate",
    ]
    assert equal
    assert cases["bubbles"]["medians"]["baseline"]["elapsed_ms"] == 5
    assert cases["bubbles"]["medians"]["candidate"]["elapsed_ms"] == 2


@pytest.mark.parametrize("inconsistent", [False, True])
def test_benchmark_mismatches_save_failing_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inconsistent: bool,
) -> None:
    """Cross-version changes and within-process nondeterminism both fail the command."""

    def measure(name: str, root: Path, warmups: int) -> dict[str, object]:
        return {
            "elapsed_ms": 1,
            "peak_rss_mib": 2,
            "consistent": not inconsistent,
            "output": {"svg": "same" if inconsistent else str(root)},
        }

    monkeypatch.setattr(bench, "run_sample", measure)
    path = tmp_path / "report.json"
    assert (
        bench.main(
            [
                "--output",
                str(path),
                "--baseline-root",
                str(tmp_path),
                "--case",
                "bubbles",
                "--repeats",
                "1",
            ],
        )
        == 1
    )
    assert json.loads(path.read_text())["outputs_equal"] is False


def test_warmups_and_instability(
    fake_solver: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warmups execute before measurement and their changed output is not ignored."""
    run = Mock(side_effect=[(SVG, DETAILS), (SVG + "\n", DETAILS), (SVG, DETAILS)])
    monkeypatch.setattr(shared, "prepare_case", lambda *_: run)
    monkeypatch.setattr(bench, "peak_rss_mib", lambda: 1.0)
    monkeypatch.setattr(
        shared,
        "environment",
        lambda: {"completed_runs": run.call_count},
    )
    row = bench.sample("1px_binary", shared.ROOT, warmups=2)
    assert run.call_count == 3
    assert row["environment"]["completed_runs"] == 3
    assert row["consistent"] is False
    assert row["elapsed_ms"] >= 0


def test_instability_between_samples_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Separately stable processes must also agree with one another."""
    rows = [
        {
            "elapsed_ms": 1,
            "peak_rss_mib": 2,
            "consistent": True,
            "output": {"svg": value},
        }
        for value in ["first", "second"]
    ]
    monkeypatch.setattr(bench, "run_sample", Mock(side_effect=rows))
    _, equal = bench.benchmark(["bubbles"], {"candidate": shared.ROOT}, 2, 0)
    assert not equal


def test_worker_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed native worker propagates its error instead of yielding a timing."""
    process = Mock(
        return_value=SimpleNamespace(returncode=7, stdout="", stderr="worker crashed"),
    )
    monkeypatch.setattr(bench.subprocess, "run", process)
    with pytest.raises(RuntimeError, match="worker crashed"):
        bench.run_sample("bubbles", shared.ROOT, 1)
    command = process.call_args.args[0]
    assert command[0] == bench.sys.executable
    assert Path(command[1]).is_absolute()
    assert process.call_args.kwargs.get("shell", False) is False


@pytest.mark.parametrize(
    "flag,value",
    [("--repeats", "0"), ("--repeats", "-1"), ("--warmups", "-1")],
)
def test_invalid_sample_counts(flag: str, value: str) -> None:
    """Invalid counts fail before any solver or worker runs."""
    with pytest.raises(SystemExit) as error:
        bench.main([flag, value])
    assert error.value.code == 2


@pytest.mark.skipif(
    bench.sys.platform != "darwin" and not bench.sys.platform.startswith("linux"),
    reason="Peak RSS measurement requires Linux or macOS",
)
def test_real_workers_are_offline_and_isolated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh workers resolve fixtures outside the repo cwd without AWS settings."""
    monkeypatch.chdir(tmp_path)
    for name in ["PORT", "S3_BUCKET", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]:
        monkeypatch.delenv(name, raising=False)
    first = bench.run_sample("1px_binary", shared.ROOT, 0)
    second = bench.run_sample("1px_binary", shared.ROOT, 0)
    assert first["pid"] != second["pid"] != os.getpid()
    assert first["output"] == second["output"]
    assert first["peak_rss_mib"] > 0
    assert first["environment"]["versions"]["numpy"]


def test_empty_bounds_are_valid_json() -> None:
    """An empty color result retains infinite bounds as JSON-safe strings."""
    svg, details = shared.prepare_case("empty-color", shared.ROOT)()
    assert details["colors"] == []
    assert details["bounds"]["left"] == "inf"
    assert details["bounds"]["width"] == "-inf"
    json.dumps(shared.fingerprint(svg, details), allow_nan=False)


def test_wrong_import_root_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An already imported checkout cannot be mistaken for another source root."""
    monkeypatch.setattr(shared.sys, "path", list(shared.sys.path))
    (tmp_path / "vectorizing").mkdir()
    (tmp_path / "vectorizing" / "__init__.py").write_text("")
    with pytest.raises(ValueError, match="different checkout"):
        shared.prepare_case("1px_binary", tmp_path)


def test_source_fingerprint(tmp_path: Path) -> None:
    """Runtime edits change provenance; test-file edits do not."""
    folder = tmp_path / "vectorizing"
    (folder / "tests").mkdir(parents=True)
    code = folder / "solver.py"
    code.write_text("first")
    before = shared.source_hash(tmp_path)
    (folder / "tests" / "test_solver.py").write_text("test")
    assert shared.source_hash(tmp_path) == before
    code.write_text("second")
    assert shared.source_hash(tmp_path) != before
