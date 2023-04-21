def coord_select (selector, p1, p2):
    return [
        selector(p1[0], p2[0]),
        selector(p1[1], p2[1])
    ]

def min_point (p1, p2):
    return coord_select(min, p1, p2)

def max_point (p1, p2):
    return coord_select(max, p1, p2)

# Computed bounds are a rough approximation
# Maybe we can do it right in the future :/
def get_curve_bounds (potrace_curve):

    start_point_x, start_point_y = potrace_curve.start_point
    top_left = [start_point_x, start_point_y]
    bottom_right = [start_point_x, start_point_y]

    for segment in potrace_curve:
        top_left = min_point(segment.end_point, top_left)
        bottom_right = max_point(segment.end_point, bottom_right)

    return [top_left, bottom_right]
    
def get_bounds (potrace_paths):
    bounds = None

    for potrace_path in potrace_paths:
        for potrace_curve in potrace_path:
            curve_bounds = get_curve_bounds(potrace_curve)

            if bounds is None:
                bounds = curve_bounds
                continue
                
            bounds[0] = min_point(curve_bounds[0], bounds[0])
            bounds[1] = max_point(curve_bounds[1], bounds[1])
    
    top_left, bottom_right = bounds
    return {
        'top': top_left[1],
        'left': top_left[0],
        'bottom': bottom_right[1],
        'right': bottom_right[0],
        'width': bottom_right[0] - top_left[0],
        'height': bottom_right[1] - top_left[1]
    }