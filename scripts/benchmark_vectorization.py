"""Measure offline solver/SVG/bounds time and fresh-process peak memory."""

import argparse
import json
import os
import statistics
import subprocess  # noqa: S404 - Only the fixed Python worker is launched.
import sys
import time
from pathlib import Path


def peak_rss_mib() -> float:
    """Convert the process high-water mark to MiB on Linux and macOS."""
    if sys.platform != "darwin" and not sys.platform.startswith("linux"):
        raise ValueError("Peak RSS measurement supports Linux and macOS only")
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024 * 1024 if sys.platform == "darwin" else 1024)


def sample(name: str, source_root: Path, warmups: int) -> dict[str, object]:
    """Warm one case, time one run and verify stable output in this fresh process."""
    from scripts._vectorization import (
        environment,
        fingerprint,
        prepare_case,
        source_hash,
    )

    run = prepare_case(name, source_root)
    revision = source_hash(source_root)
    expected = None
    consistent = True
    for _ in range(warmups + 1):
        start = time.perf_counter()
        svg, details = run()
        elapsed = (time.perf_counter() - start) * 1000
        output = fingerprint(svg, details)
        if expected is not None and expected != output:
            consistent = False
        expected = output
    runtime = environment()
    return {
        "elapsed_ms": elapsed,
        "peak_rss_mib": peak_rss_mib(),
        "output": output,
        "consistent": consistent,
        "environment": runtime,
        "pid": os.getpid(),
        "source_sha256": revision,
    }


def run_sample(name: str, source_root: Path, warmups: int) -> dict[str, object]:
    """Run this script in a new interpreter, propagating worker failures."""
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--case",
        name,
        "--source-root",
        str(source_root),
        "--warmups",
        str(warmups),
    ]
    # The executable and script are fixed; arguments are passed without a shell.
    result = subprocess.run(command, capture_output=True, text=True)  # noqa: S603
    if result.returncode:
        raise RuntimeError(
            f"Benchmark worker failed for {name}: {result.stderr.strip()}",
        )
    return json.loads(result.stdout)


def benchmark(
    names: list[str],
    roots: dict[str, Path],
    repeats: int,
    warmups: int,
) -> tuple[dict[str, object], bool]:
    """Alternate variants, retaining raw samples and exact-output equality checks."""
    cases = {}
    all_equal = True
    for name in names:
        samples = {variant: [] for variant in roots}
        for iteration in range(repeats):
            order = list(roots) if iteration % 2 == 0 else list(reversed(roots))
            for variant in order:
                samples[variant].append(run_sample(name, roots[variant], warmups))
        reference = next(iter(samples.values()))[0]["output"]
        equal = all(
            row["consistent"] and row["output"] == reference
            for rows in samples.values()
            for row in rows
        )
        all_equal &= equal
        medians = {
            variant: {
                "elapsed_ms": statistics.median(row["elapsed_ms"] for row in rows),
                "peak_rss_mib": statistics.median(row["peak_rss_mib"] for row in rows),
            }
            for variant, rows in samples.items()
        }
        cases[name] = {"samples": samples, "medians": medians, "outputs_equal": equal}
        for variant, values in medians.items():
            print(
                f"{name} {variant}: {values['elapsed_ms']:.2f} ms, "
                f"{values['peak_rss_mib']:.2f} MiB",
            )
        if not equal:
            print(
                f"{name}: outputs differ; timings are not an equivalent comparison.",
                file=sys.stderr,
            )
    return cases, all_equal


def positive(value: str) -> int:
    """Require at least one measured sample."""
    count = int(value)
    if count < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return count


def nonnegative(value: str) -> int:
    """Allow zero warmups, but reject negative counts."""
    count = int(value)
    if count < 0:
        raise argparse.ArgumentTypeError("must be at least 0")
    return count


def main(argv: list[str] | None = None) -> int:
    """Write a benchmark report, returning one when any outputs differ."""
    from scripts._vectorization import CASES, ROOT

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON report path (required)")
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="Trusted candidate checkout",
    )
    parser.add_argument(
        "--baseline-root",
        type=Path,
        help="Optional trusted baseline checkout",
    )
    parser.add_argument(
        "--case",
        action="append",
        choices=CASES,
        help="Repeat to select cases; default: all",
    )
    parser.add_argument("--repeats", type=positive, default=3)
    parser.add_argument(
        "--warmups",
        type=nonnegative,
        default=1,
        help="Warmups per fresh process",
    )
    parser.add_argument(
        "--label",
        help="Optional revisions or description for this report",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    names = list(dict.fromkeys(args.case or CASES))
    try:
        if args.worker:
            if len(names) != 1:
                raise ValueError("A worker measures exactly one case")
            print(
                json.dumps(
                    sample(names[0], args.source_root, args.warmups),
                    allow_nan=False,
                ),
            )
            return 0
        if args.output is None:
            raise ValueError("--output is required")
        if args.output.exists():
            raise ValueError(f"Refusing to overwrite: {args.output}")
        roots = {"baseline": args.baseline_root.resolve()} if args.baseline_root else {}
        roots["candidate"] = args.source_root.resolve()
        cases, equal = benchmark(names, roots, args.repeats, args.warmups)
        report = {
            "schema_version": 1,
            "label": args.label,
            "source_roots": {name: str(path) for name, path in roots.items()},
            "repeats": args.repeats,
            "warmups_per_process": args.warmups,
            "timing_scope": "solver, SVG serialization, colors, dimensions and bounds",
            "rss_scope": "fresh process: imports, input, warmups, output checks",
            "cases": cases,
            "outputs_equal": equal,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as destination:
            json.dump(report, destination, indent=2, sort_keys=True, allow_nan=False)
            destination.write("\n")
        return int(not equal)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
