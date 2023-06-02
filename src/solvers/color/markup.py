def to_SVG_color(color):
    func = 'rgb' if len(color) == 3 else 'rgba'
    tuple = ''.join([f'{item},' if i != len(color) - 1 else f'{item}' for i, item in enumerate(color)])
    return f'{func}({tuple})'

def create_markup(geo, colors, img_info):
    img_width = img_info.width
    img_height = img_info.height

    paths_markup = []

    for compound_path, color in zip(geo, colors):
        d = ''
        for path in compound_path:
            for idx, geo_item in enumerate(path):
                d += geo_item.draw(from_start = idx == 0)
        d += 'Z'
        path_markup = f'<path d="{d}" fill="{to_SVG_color(color)}" />'
        paths_markup.append(path_markup)
    
    paths_markup = '\n'.join(paths_markup)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{img_width}" height="{img_height}" viewBox="0 0 {img_width} {img_height}">\n'
        f'<g>\n{paths_markup}\n</g>\n'
        f'</svg>'
    )