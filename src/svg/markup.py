from svg.draw import draw_geo

# Converts a color to a valid svg color value
def to_SVG_color(color):
    func = 'rgb' if len(color) == 3 else 'rgba'
    tuple = ''.join([f'{item},' if i != len(color) - 1 else f'{item}' for i, item in enumerate(color)])
    return f'{func}({tuple})'

# Creates markup of traced paths
def create_markup(compound_paths, colors, width, height):
    paths_markup = []

    for compound_path, color in zip(compound_paths, colors):
        if not len(compound_path):
            continue

        d = ''.join([draw_geo(geo, i == 0) for path in compound_path for i, geo in enumerate(path)]) + 'Z'
        path_markup = f'<path d="{d}" fill="{to_SVG_color(color)}" />'
        paths_markup.append(path_markup)

    paths_markup = '\n'.join(paths_markup)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f'<g>\n{paths_markup}\n</g>\n'
        f'</svg>'
    )