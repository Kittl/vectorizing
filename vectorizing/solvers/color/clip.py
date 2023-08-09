import pyclipper

from vectorizing.geometry.potrace import (
    potrace_path_to_compound_path,
    compound_path_to_compound_polygon,
    compound_polygon_to_compound_path
)

SCALE = 1_000_000

# Ensures paths are disjoint after tracing.
# See bitmaps.py for why this is important.

# NOTE: The clipper library uses integer coordinates only for numerical robustness.
# That's why coordinates are scaled by a big factor, to preserve precision.
def remove_layering(traced_bitmaps):
    compound_paths = [
        potrace_path_to_compound_path(traced) 
        for traced in traced_bitmaps
    ]

    compound_polygons = [
        compound_path_to_compound_polygon(compound_path, SCALE) 
        for compound_path in compound_paths
    ]

    for x in range(len(compound_polygons) - 1):
        next = compound_polygons[x + 1]

        pc = pyclipper.Pyclipper()
        pc.AddPaths(next, pyclipper.PT_CLIP, True)
        pc.AddPaths(compound_polygons[x], pyclipper.PT_SUBJECT, True)

        compound_polygons[x] = pc.Execute(
            pyclipper.CT_DIFFERENCE, 
            pyclipper.PFT_EVENODD, 
            pyclipper.PFT_EVENODD
        )

    compound_paths = [
        compound_polygon_to_compound_path(compound_polygon, 1 / SCALE) 
        for compound_polygon in compound_polygons
    ]

    return compound_paths