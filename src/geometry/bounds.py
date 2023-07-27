import numpy as np

# Class that represents a bounds object
class Bounds:
    def __init__(self, min_x, min_y, max_x, max_y):
        self.min_x = min_x
        self.min_y = min_y
        self.max_x = max_x
        self.max_y = max_y
    
    def to_dict(self):
        return {
            'top': self.min_y,
            'left': self.min_x,
            'bottom': self.max_y,
            'right': self.max_x,
            'width': self.max_x - self.min_x,
            'height': self.max_y - self.min_y
        }

# Given a list of bounds, it will compute the total bounds.
# Meaning, the tightest bounds that contain all the bounds in the list.
def compute_total_bounds(bounds_list):
    min_x = [bounds.min_x for bounds in bounds_list]
    min_y = [bounds.min_y for bounds in bounds_list]
    max_x = [bounds.max_x for bounds in bounds_list]
    max_y = [bounds.max_y for bounds in bounds_list]

    return Bounds(
        min(min_x),
        min(min_y),
        max(max_x),
        max(max_y)
    )

# Calculates bounds of a path made out CubicBeziers and SegmentLists
def path_bounds(path):
    bounds = [item.bounds() for item in path]
    return compute_total_bounds(bounds)

# Calculates bounds of a compound path, meaning a list of paths
def compound_path_bounds(compound_path):
    bounds = [path_bounds(path) for path in compound_path]
    return compute_total_bounds(bounds)

# Calculates bounds of a list of compound paths
def compound_path_list_bounds(compound_path_list):
    bounds = [
        compound_path_bounds(compound_path) 
        for compound_path in compound_path_list
        if len(compound_path) > 0
    ]
    return compute_total_bounds(bounds)