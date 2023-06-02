import numpy as np

from geometry.corner import Corner
from geometry.cubic_bezier import CubicBezier

import pyclipper

def extract_geo(potrace_path):
    geo = []

    for potrace_curve in potrace_path:
        curve = []

        start_x, start_y = potrace_curve.start_point
        for segment in potrace_curve:
            end_x, end_y = segment.end_point
            start = np.array([start_x, start_y])
            end = np.array([end_x, end_y])

            if segment.is_corner:
                c_x, c_y = segment.c
                c = np.array([c_x, c_y])
                curve.append(Corner(start, c, end))
            
            else:
                c1_x, c1_y = segment.c1
                c2_x, c2_y = segment.c2
                p1 = np.array([c1_x, c1_y])
                p2 = np.array([c2_x, c2_y])
                curve.append(CubicBezier(start, p1, p2, end))
            
            start_x = end_x
            start_y = end_y

        geo.append(curve)
    
    return geo
            
def extract_clipper_geo(potrace_path, scale = 1):
    geo = extract_geo(potrace_path)
    
    polygons = []
    for curve in geo:
        polygon = []
        for item in curve:
            polygon += item.to_clipper_geo(scale)
        polygons.append(polygon)

    return polygons

def extract_clipper_geo_multiple(potrace_paths, scale = 1):
    geo = []
    for potrace_path in potrace_paths:
        geo += extract_clipper_geo(potrace_path, scale)
    return geo

subj = [
    [np.array([180, 200]), [260, 200], [260, 150], [180, 150]],
    [[215, 160], [230, 190], [200, 190]]
]

clip = [[190, 210], [240, 210], [240, 130], [190, 130]]

pc = pyclipper.Pyclipper()
pc.AddPath(clip, pyclipper.PT_CLIP, True)
pc.AddPaths(subj, pyclipper.PT_SUBJECT, True)

solution = pc.Execute(pyclipper.CT_INTERSECTION, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD)