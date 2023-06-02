from solvers.util import truncate

class SegmentList:
    def __init__(self, points):
        self.start = points[0]
        self.points = points

    def scale(self, s):
        self.start *= s
        self.points *= s

    def flattened(self):
        return self
    
    def to_list(self):
        return self.points
    
    def draw(self, from_start = False):
        m = ''
        l = ''

        if from_start:
            m +=  f'M {truncate(self.start[0])},{truncate(self.start[1])} '
        
        l += ' '.join([f'L {truncate(point[0])},{truncate(point[1])}' for point in self.points[1:]])

        return m + l + ' '