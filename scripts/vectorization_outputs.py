"""Capture local fixtures and compare exact SVG, pixel and solver outputs."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def capture(
    output: Path,
    names: list[str],
    source_root: Path,
    label: str | None,
) -> None:
    """Write a complete manifest last, refusing to replace existing artifacts."""
    from cairosvg import svg2png

    from scripts._vectorization import (
        environment,
        fingerprint,
        prepare_case,
        source_hash,
    )

    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"Output must be a new or empty directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    cases = {}
    for name in names:
        svg, details = prepare_case(name, source_root)()
        svg_bytes = svg.encode("utf-8")
        for extension, data in {
            "svg": svg_bytes,
            "png": svg2png(bytestring=svg_bytes),
        }.items():
            with (output / f"{name}.{extension}").open("xb") as artifact:
                artifact.write(data)
        pixel_hash, shape = pixels(output / f"{name}.png")
        cases[name] = {
            **fingerprint(svg, details),
            "rgba_sha256": pixel_hash,
            "rgba_shape": shape,
        }
        print(f"Captured {name}")
    report = {
        "schema_version": 1,
        "label": label,
        "source_root": str(source_root.resolve()),
        "source_sha256": source_hash(source_root),
        "environment": environment(),
        "cases": cases,
    }
    with (output / "outputs.json").open("x", encoding="utf-8") as destination:
        json.dump(report, destination, indent=2, sort_keys=True, allow_nan=False)
        destination.write("\n")


def pixels(path: Path) -> tuple[str, list[int]]:
    """Hash decoded RGBA pixels, independent of PNG compression."""
    from PIL import Image

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        return hashlib.sha256(rgba.tobytes()).hexdigest(), [rgba.height, rgba.width, 4]


def read_capture(folder: Path) -> dict[str, object]:
    """Validate a manifest and its SVG/PNG artifacts before trusting its hashes."""
    from scripts._vectorization import CASES, file_hash

    report = json.loads((folder / "outputs.json").read_text(encoding="utf-8"))
    # Reject non-standard NaN/Infinity literals in edited or external reports.
    json.dumps(report, allow_nan=False)
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError(f"Unsupported capture format: {folder}")
    cases = report.get("cases")
    if not isinstance(cases, dict) or not cases:
        raise ValueError(f"Capture has no cases: {folder}")
    required = {
        "input",
        "colors",
        "colors_dtype",
        "dimensions",
        "bounds",
        "svg_sha256",
        "rgba_sha256",
        "rgba_shape",
    }
    for name, record in cases.items():
        if (
            name not in CASES
            or not isinstance(record, dict)
            or not required <= record.keys()
        ):
            raise ValueError(f"Invalid capture case: {name}")
        if file_hash(folder / f"{name}.svg") != record["svg_sha256"]:
            raise ValueError(f"SVG does not match its manifest: {folder}/{name}")
        digest, shape = pixels(folder / f"{name}.png")
        if digest != record["rgba_sha256"] or shape != record["rgba_shape"]:
            raise ValueError(f"PNG does not match its manifest: {folder}/{name}")
    return report


def compare(baseline: Path, candidate: Path) -> int:
    """Return one for changed outputs or case sets, and zero for exact equality."""
    before, after = read_capture(baseline), read_capture(candidate)
    old, new = before["cases"], after["cases"]
    changed = False
    for name in sorted(old.keys() | new.keys()):
        if name not in old or name not in new:
            print(f"{name}: {'added' if name in new else 'missing'} case")
            changed = True
        elif old[name] != new[name]:
            fields = sorted(
                key
                for key in old[name].keys() | new[name].keys()
                if key not in old[name]
                or key not in new[name]
                or old[name][key] != new[name][key]
            )
            print(f"{name}: changed {', '.join(fields)}")
            changed = True
    if before.get("environment") != after.get("environment"):
        print(
            "Note: capture environments differ; see outputs.json metadata.",
            file=sys.stderr,
        )
    if not changed:
        print(f"All {len(old)} cases match exactly.")
    return int(changed)


def main(argv: list[str] | None = None) -> int:
    """Capture outputs or compare two saved directories without AWS access."""
    from scripts._vectorization import CASES, ROOT

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("capture", help="Save SVGs, PNGs and a JSON manifest")
    save.add_argument("output", type=Path)
    save.add_argument(
        "--source-root",
        type=Path,
        default=ROOT,
        help="Trusted checkout to run",
    )
    save.add_argument(
        "--case",
        action="append",
        choices=CASES,
        help="Repeat to select cases; default: all",
    )
    save.add_argument(
        "--label",
        help="Optional revision or description for the manifest",
    )
    diff = commands.add_parser(
        "compare",
        help="Compare complete captures; exit 1 on changes",
    )
    diff.add_argument("baseline", type=Path)
    diff.add_argument("candidate", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            return compare(args.baseline, args.candidate)
        capture(
            args.output,
            list(dict.fromkeys(args.case or CASES)),
            args.source_root,
            args.label,
        )
        return 0
    except (OSError, ValueError, ImportError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
