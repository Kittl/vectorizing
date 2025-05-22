import numpy as np

from vectorizing.geometry.bounds import Bounds


# Class to represent a list of segments
# IMPORTANT: points should be an ndarray, and not a python list
class SegmentList:
    def __init__(self, points):
        self.start = points[0]
        self.points = points

    def scaled(self, s):
        return SegmentList(self.points * s)

    def flattened(self, _):
        return self

    def to_list(self):
        return list(self.points)

    def bounds(self):
        t = self.points.T
        x = t[0]
        y = t[1]

        return Bounds(np.min(x), np.min(y), np.max(x), np.max(y))

    @staticmethod
    def from_polygon(polygon):
        return SegmentList(np.array(polygon))
