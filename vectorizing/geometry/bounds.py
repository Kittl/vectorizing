import numpy as np


# Calculates bounds of a list of compound paths
def compound_paths_bounds(compound_paths):
    """
    Calculates the combined bounds of a list of compound paths.

        Parameters:
            compound_paths: The list of compound paths (SKPath).

        Returns:
            An object containing combined bounds info.
    """
    min_x = np.inf
    min_y = np.inf
    max_x = -np.inf
    max_y = -np.inf

    for compound_path in compound_paths:
        l, t, r, b = compound_path.bounds
        min_x = min(min_x, l)
        min_y = min(min_y, t)
        max_x = max(max_x, r)
        max_y = max(max_y, b)

    return {
        "top": min_y,
        "left": min_x,
        "bottom": max_y,
        "right": max_x,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }
