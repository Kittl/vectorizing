import numpy as np

from vectorizing.geometry.segment_list import SegmentList
from vectorizing.geometry.cubic_bezier import CubicBezier

# Given a potrace path, it constructs a compound path
# using SegmentList and CubicBezier
def potrace_path_to_compound_path(potrace_path):
    compound_path = []

    for potrace_curve in potrace_path:
        path = []

        start_x, start_y = potrace_curve.start_point
        for segment in potrace_curve:
            end_x, end_y = segment.end_point
            start = np.array([start_x, start_y])
            end = np.array([end_x, end_y])

            if segment.is_corner:
                c_x, c_y = segment.c
                c = np.array([c_x, c_y])
                path.append(SegmentList(np.array([start, c, end])))
            
            else:
                c1_x, c1_y = segment.c1
                c2_x, c2_y = segment.c2
                p1 = np.array([c1_x, c1_y])
                p2 = np.array([c2_x, c2_y])
                path.append(CubicBezier(start, p1, p2, end))
            
            start_x = end_x
            start_y = end_y

        compound_path.append(path)
    
    return compound_path

# "Unfolds" a folded polygon, meaning:
# A polygon that can be written in the form p = [...SegmentList, ...SegmentList, ...]
# In the end, p can be written as p = [...SegmentList] 
def unfold_polygon(folded_polygon):
    unfolded = []
    poly_length = len(folded_polygon)

    for idx, segment_list in enumerate(folded_polygon):
        point_list = segment_list.to_list()
        if idx == poly_length - 1:
            unfolded += point_list
        else:
            unfolded += point_list[:len(point_list) - 1]
    
    return unfolded

# Given a compound path, it converts it to a compound polygon
# by flattening curves.
# All coordinates can be scaled for convenience (see pyclipper)
def compound_path_to_compound_polygon(compound_path, scale = 1):
    polygons = [[item.flattened().scaled(scale) for item in path] for path in compound_path]
    return [unfold_polygon(folded_polygon) for folded_polygon in polygons]

# Given a compound polygon, it converts it to a compound path.
# All coordinates can be scaled for convenience (see pyclipper)
def compound_polygon_to_compound_path(compound_polygon, scale = 1):
    return [[SegmentList.from_polygon(polygon).scaled(scale)] for polygon in compound_polygon]