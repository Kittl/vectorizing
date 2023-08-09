from vectorizing.geometry.cubic_bezier import CubicBezier
from vectorizing.geometry.segment_list import SegmentList

# Truncates a number to 2 decimal places
def truncate(number):
    return "{:.2f}".format(number)

# Draws a segment list's path data
def draw_segment_list(segment_list, first_in_path = False):
    l = ' '.join([
        f'L {truncate(point[0])},{truncate(point[1])}' 
        for point in segment_list.points[1:]
    ]) + ' '

    if first_in_path:
        m = f'M {truncate(segment_list.start[0])},{truncate(segment_list.start[1])} '
        return m + l
    
    return l

# Draws a cubic bezier path data
def draw_cubic_bezier(cubic_bezier, first_in_path = False):
    c = 'C' \
        f'{truncate(cubic_bezier.p1[0])},{truncate(cubic_bezier.p1[1])} ' \
        f'{truncate(cubic_bezier.p2[0])},{truncate(cubic_bezier.p2[1])} ' \
        f'{truncate(cubic_bezier.p3[0])},{truncate(cubic_bezier.p3[1])} '

    if first_in_path:
        m = f'M {truncate(cubic_bezier.p0[0])},{truncate(cubic_bezier.p0[1])} '
        return m + c
    
    return c

class UnknownGeometricEntity (Exception):
    def __init__ (self):
        super().__init__(self, 'draw_geo: Unknown geometric entity.')

def draw_geo(geo, first_in_path = False):
    if isinstance(geo, CubicBezier):
        return draw_cubic_bezier(geo, first_in_path)
    if isinstance(geo, SegmentList):
        return draw_segment_list(geo, first_in_path)
    raise UnknownGeometricEntity()