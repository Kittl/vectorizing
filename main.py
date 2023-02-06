from export import build_markup, svg_wrap
from processing import process

URL = 'https://images.unsplash.com/photo-1675458884693-9322658334d8?ixlib=rb-4.0.3&ixid=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=776&q=80'

traced_bitmaps, colors, img_height, img_width = process(URL, True)

markup = build_markup(traced_bitmaps, colors)
svg = svg_wrap(markup, img_height, img_width)

file = open('output.svg', 'w')
file.write(svg)
file.close()