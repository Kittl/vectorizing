import numpy as np
from vectorizing.geometry.segment_list import SegmentList
from numba import njit

# Flattening approach is inspired in
# https://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.86.162&rep=rep1&type=pdf

@njit
def is_flat_enough(points, tol = .2):
    p0 = points[0]
    p1 = points[1]
    p2 = points[2]
    p3 = points[3]

    ux = 3 * p1[0] - 2 * p0[0] - p3[0]
    uy = 3 * p1[1] - 2 * p0[1] - p3[1]
    vx = 3 * p2[0] - 2 * p3[0] - p0[0]
    vy = 3 * p2[1] - 2 * p3[1] - p0[1]
    
    ux = ux ** 2
    uy = uy ** 2
    vx = vx ** 2
    vy = vy ** 2

    if ux < vx:
        ux = vx
    
    if uy < vy:
        uy = vy
    
    tolerance = 16 * tol ** 2
    return ux + uy <= tolerance

@njit
def subdivide(points):
    p0 = points[0]
    p1 = points[1]
    p2 = points[2]
    p3 = points[3]

    l0 = p0
    r3 = p3

    l1 = (
        (p0[0] + p1[0]) / 2,
        (p0[1] + p1[1]) / 2
    )

    r2 = (
        (p2[0] + p3[0]) / 2,
        (p2[1] + p3[1]) / 2
    )

    m = (
        (p1[0] + p2[0]) / 2,
        (p1[1] + p2[1]) / 2
    )

    l2 = (
        (m[0] + l1[0]) / 2,
        (m[1] + l1[1]) / 2,
    )

    r1 = (
        (m[0] + r2[0]) / 2,
        (m[1] + r2[1]) / 2
    )

    j = (
        (l2[0] + r1[0]) / 2,
        (l2[1] + r1[1]) / 2
    )

    l3 = r0 = j
    
    return (
        (l0, l1, l2, l3), 
        (r0, r1, r2, r3)
    )

@njit
def flatten(points, tolerance):
    stack = [points]
    flattened = []

    while len(stack):
        first = stack.pop()

        if is_flat_enough(first, tolerance):
            flattened.append(first[0])
            flattened.append(first[1])
        
        else:
            subdivision = subdivide(first)
            stack.append(subdivision[1])
            stack.append(subdivision[0])
    
    return flattened

# Class to represent a cubic bezier
class CubicBezier:
    def __init__(self, p0, p1, p2, p3):
        self.p0 = p0
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3
    
    def scaled(self, s):
        return CubicBezier(
            self.p0 * s,
            self.p1 * s,
            self.p2 * s,
            self.p3 * s
        )
    
    def flattened(self, tolerance):
        points = (tuple(self.p0), tuple(self.p1), tuple(self.p2), tuple(self.p3))
        return SegmentList(np.array(flatten(points, tolerance)))
    
    def bounds(self, tolerance):
        return self.flattened(tolerance).bounds(tolerance)