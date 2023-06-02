"""

Potrace bindings are minimal and contain no way to convert resulting paths
into SVG markup. This script handles that.

For reference, check https://pythonhosted.org/pypotrace/ref.html

"""

import numpy as np
from random import randint

from geometry.potrace import extract_clipper_geo_multiple
import pyclipper

def tuple_to_string (tuple):
    return ''.join(
        ['('] + 
        [f'{item},' if i != len(tuple) - 1 else f'{item}' for i, item in enumerate(tuple)] +
        [')']
    )

def truncate (number):
    return "{:.2f}".format(number)

def build_corner (segment):
    end_point_x, end_point_y = segment.end_point
    c_x, c_y = segment.c
    return f'L {truncate(c_x)},{truncate(c_y)} L {truncate(end_point_x)},{truncate(end_point_y)}'

def build_cubic_bezier (segment):
    end_point_x, end_point_y = segment.end_point
    c1_x, c1_y = segment.c1
    c2_x, c2_y = segment.c2
    return f'C {truncate(c1_x)},{truncate(c1_y)} {truncate(c2_x)},{truncate(c2_y)} {truncate(end_point_x)},{truncate(end_point_y)}'

def build_curve_path_data (potrace_curve):
    
    start_point_x, start_point_y = potrace_curve.start_point
    commands = [f'M {start_point_x},{start_point_y}']

    for segment in potrace_curve:

        if segment.is_corner:
            command = build_corner(segment)

        else:
            command = build_cubic_bezier(segment)
        
        commands.append(command)

    commands.append('Z')
    return ' '.join(commands)
    
def build_path_markup (potrace_path, color):
    
    curves_path_data_items = [
        build_curve_path_data(potrace_curve) 
        for potrace_curve in potrace_path
    ]
    
    path_data = ' '.join(curves_path_data_items)
    return f'<path d="{path_data}" fill="rgba{tuple_to_string(color)}" />'

def test(potrace_paths, width, height):
    scale = 1
    subject = extract_clipper_geo_multiple(potrace_paths, scale)
    return subject
    clip = [
        [-10, -10],
        [width * scale + 10, -10],
        [width * scale + 10, height * scale + 10],
        [-10, height* scale + 10]
    ]

    pc = pyclipper.Pyclipper()
    pc.AddPath(clip, pyclipper.PT_SUBJECT, True)
    pc.AddPaths(subject, pyclipper.PT_CLIP, True)
    solution = pc.Execute(pyclipper.CT_DIFFERENCE, pyclipper.PFT_EVENODD, pyclipper.PFT_EVENODD)
    return solution

def build_markup (potrace_paths, colors, img_width, img_height):
    xor = test(potrace_paths, img_width, img_height)
    print(len(xor))

    ds = []
    for polygon in xor:
        d = ''
        for x in range(len(polygon)):
            point = polygon[x]
            if x == 0:
                d += f'M {point[0]} {point[1]} '
            else:
                d += f'L {point[0]} {point[1]} '
        d += 'Z'
        ds.append(d)

    new_colors = []
    for x in range(len(potrace_paths)):
        potrace_path = potrace_paths[x]
        concat = []
        for _ in potrace_path:
            concat.append(colors[x])
        new_colors += concat

    print(new_colors)

    xor_markup = '\n'.join([
        f'<path d="{d}" fill="rgba{tuple_to_string(new_colors[z])}"/>'
        for z, d in enumerate(ds)
    ])
    
    paths_markup_items = [
        build_path_markup(potrace_path, color)
        for potrace_path, color in zip(potrace_paths, colors)
    ]

    paths_markup = '\n'.join(paths_markup_items)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{img_width}" height="{img_height}" viewBox="0 0 {img_width} {img_height}">\n'
        #f'<g>\n{paths_markup}\n</g>\n'
        f'<g>\n{xor_markup}\n</g>\n'
        f'</svg>'
    )