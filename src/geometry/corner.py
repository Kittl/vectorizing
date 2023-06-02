class Corner:
    def __init__(self, start, mid, end):
        self.start = start
        self.mid = mid
        self.end = end

    def to_clipper_geo(self, scale = 1):
        return [
            self.start * scale, 
            self.mid * scale, 
            self.end * scale
        ]

    def move_to(self):
        return f'M {self.start[0]},{self.start[1]} '

    def draw(self):
        return f'L {self.mid[0]},{self.mid[1]} L {self.end[0]},{self.end[1]} '