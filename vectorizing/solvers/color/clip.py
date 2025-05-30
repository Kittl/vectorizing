from pathops import op, PathOp
from vectorizing.geometry.potrace import potrace_path_to_compound_path


# Ensures paths are disjoint after tracing.
# See bitmaps.py for why this is important.
def remove_layering(traced_bitmaps):
    compound_paths = [
        potrace_path_to_compound_path(traced) for traced in traced_bitmaps
    ]

    for x in range(len(compound_paths) - 1):
        next = compound_paths[x + 1]
        compound_paths[x] = op(compound_paths[x], next, PathOp.DIFFERENCE)

    return compound_paths
