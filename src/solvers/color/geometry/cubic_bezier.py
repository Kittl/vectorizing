import numpy as np
from solvers.color.geometry.segment_list import SegmentList
from solvers.util import truncate

class CubicBezier:
    def __init__(self, p0, p1, p2, p3):
        self.p0 = p0
        self.p1 = p1
        self.p2 = p2
        self.p3 = p3

    def evaluate(self, t):
        if t < 0: 
            t = 0
        
        if t > 1:
            t = 1
        
        return (
            (1 - t) ** 3 * self.p0 +
            3 * (1 - t) ** 2 * t * self.p1 +
            3 * (1 - t) * t ** 2 * self.p2 +
            t ** 3 * self.p3
        )
    
    def subdivide(self):
        l0 = self.p0
        r3 = self.p3

        p0_p1 = np.array([self.p0, self.p1])
        p1_p2 = np.array([self.p1, self.p2])
        p2_p3 = np.array([self.p2, self.p3])

        l1 = np.sum(p0_p1, axis = 0) / 2
        r2 = np.sum(p2_p3, axis = 0) / 2
        m = np.sum(p1_p2, axis = 0) / 2
        
        m_l1 = np.array([m, l1])
        m_r2 = np.array([m, r2])

        l2 = np.sum(m_l1, axis = 0) / 2
        r1 = np.sum(m_r2, axis = 0) / 2

        l2_r1 = np.array([l2, r1])
        j = np.sum(l2_r1, axis = 0) / 2
        l3 = r0 = j

        return CubicBezier(l0, l1, l2, l3), CubicBezier(r0, r1, r2, r3)

    def is_flat_enough(self, tol = 1e-1):
        ux = 3 * self.p1[0] - 2 * self.p0[0] - self.p3[0]
        uy = 3 * self.p1[1] - 2 * self.p0[1] - self.p3[1]
        vx = 3 * self.p2[0] - 2 * self.p3[0] - self.p0[0]
        vy = 3 * self.p2[1] - 2 * self.p3[1] - self.p0[1]
        
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
    
    def scale(self, s):
        self.p0 *= s
        self.p1 *= s
        self.p2 *= s
        self.p3 *= s

    def flatten(self):
        if self.is_flat_enough():
            return [self.p0, self.p3]

        c1, c2 = self.subdivide()
        return c1.flatten() + c2.flatten()
    
    def flattened(self):
        return SegmentList(self.flatten())
    
    def draw(self, from_start = False):
        m = ''
        l = ''

        if from_start:
            m += f'M {truncate(self.p0[0])},{truncate(self.p0[1])} '
        
        l = f'C {truncate(self.p1[0])},{truncate(self.p1[1])} {truncate(self.p2[0])},{truncate(self.p2[1])} {truncate(self.p3[0])},{truncate(self.p3[1])} '
        return m + l