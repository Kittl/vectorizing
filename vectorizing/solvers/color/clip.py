from pathops import op, PathOp, Path
from vectorizing.geometry.potrace import potrace_path_to_compound_path

def create_background_rect(img, padding):
    """
    Creates a rectangle that matches the image dimensions plus
    some padding.

        Parameters:
            img: A Pillow image instance.

        Returns:
            The rectangle.
    """
    rect = Path()
    rect.moveTo(-padding, -padding)
    rect.lineTo(img.width + padding, -padding)
    rect.lineTo(img.width + padding, img.height + padding)
    rect.lineTo(-padding, img.height + padding)
    rect.close()
    return rect

def remove_layering(traced_bitmaps, img):
    """
    Performs boolean operations on a list of traced bitmaps
    to ensure that they are all disjoint.

    This function uses a technique devised to try to minimize
    the holes created / outright failures of SKPath boolean operations.
    Even so, a failure can still happen (and often does), particularly
    for very intricate paths (usually coming from real world photographs).
    In such cases, the routine fallbacks to a mixture of disjoint paths
    (the ones for which the boolean operations didn't fail), and layered paths.

        Parameters:
            traced_bitmaps: The list of traced bitmaps (potrace paths).
            img: A Pillow image.

        Returns:
            The processed list of compound paths.
    """
    compound_paths = [
        potrace_path_to_compound_path(traced) for traced in traced_bitmaps
    ]

    disjoint_paths = []
    for x in range(len(compound_paths) - 1):
        # Each base path has bigger padding to reduce
        # the amount of overlapping borders.
        base = create_background_rect(img, (x + 1) * 10)
        
        to_subtract = Path()
        for y in range(0, x):
            to_subtract.addPath(disjoint_paths[y])
        to_subtract.addPath(compound_paths[x + 1])

        try:
            result = op(base, to_subtract, PathOp.DIFFERENCE)
        except:
            break
        disjoint_paths.append(result)

    for x in range(len(disjoint_paths)):
        try:
            disjoint_paths[x] = op(disjoint_paths[x], create_background_rect(img, 0), PathOp.INTERSECTION)
        except:
            return compound_paths

    disjoint_paths = disjoint_paths + compound_paths[len(disjoint_paths) : len(compound_paths)]
    return disjoint_paths
