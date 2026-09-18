"""Restore the pre-overlap layer clipping, including its legacy error fallback."""

import potrace
from pathops import Path, PathOp, PathOpsError, op
from PIL import Image

from vectorizing.geometry.potrace import potrace_path_to_compound_path


def create_background_rect(img: Image.Image, padding: int) -> Path:
    """Return the image rectangle expanded by padding on every side."""
    rect = Path()
    rect.moveTo(-padding, -padding)
    rect.lineTo(img.width + padding, -padding)
    rect.lineTo(img.width + padding, img.height + padding)
    rect.lineTo(-padding, img.height + padding)
    rect.close()
    return rect


def remove_layering(
    traced_bitmaps: list[potrace.Path],
    img: Image.Image,
    has_background: bool,
) -> list[Path]:
    """Cut later colors out of lower layers using the original clipping routine."""
    # Preserve the original PathOps-error fallback for this rollback. Complex
    # paths can still retain overlap if clipping fails; shared edges can seam.
    compound_paths = [
        potrace_path_to_compound_path(traced) for traced in traced_bitmaps
    ]
    if has_background:
        for index in range(len(compound_paths) - 1):
            try:
                compound_paths[index] = op(
                    compound_paths[index],
                    compound_paths[index + 1],
                    PathOp.DIFFERENCE,
                )
            except PathOpsError:
                break
        return compound_paths

    disjoint_paths = []
    for index in range(len(compound_paths) - 1):
        # The old routine uses successively padded rectangles, then clips back
        # to the image bounds. Keep that behavior separate from the rim change.
        base = create_background_rect(img, (index + 1) * 10)
        to_subtract = Path()
        for previous in disjoint_paths:
            to_subtract.addPath(previous)
        to_subtract.addPath(compound_paths[index + 1])
        try:
            result = op(base, to_subtract, PathOp.DIFFERENCE)
        except PathOpsError:
            break
        disjoint_paths.append(result)

    for index, path in enumerate(disjoint_paths):
        try:
            disjoint_paths[index] = op(
                path,
                create_background_rect(img, 0),
                PathOp.INTERSECTION,
            )
        except PathOpsError:
            return compound_paths
    processed = len(disjoint_paths)
    return disjoint_paths + compound_paths[processed:]
