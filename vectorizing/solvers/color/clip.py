from pathops import op, PathOp
from vectorizing.geometry.potrace import potrace_path_to_compound_path

def remove_layering(traced_bitmaps):
    """
    Performs boolean operations on a list of traced bitmaps
    to ensure that they are all disjoint.

            Parameters:
                traced_bitmaps: The list of traced bitmaps (potrace paths).

            Returns:
                The processed list of compound paths.
    """
    compound_paths = [
        potrace_path_to_compound_path(traced) for traced in traced_bitmaps
    ]

    for x in range(len(compound_paths) - 1):
        next = compound_paths[x + 1]
        compound_paths[x] = op(compound_paths[x], next, PathOp.DIFFERENCE)

    return compound_paths
