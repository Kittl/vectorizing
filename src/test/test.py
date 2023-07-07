import os

from util.read import try_read_image_from_path
from solvers.color.ColorSolver import ColorSolver
from solvers.binary.BinarySolver import BinarySolver
from svg.markup import create_markup

# File meant for primitive manual testing.
# Images in the test-images directory are processed.
# The results are placed in test-results.

NUM_COLORS = 6
formats = ['jpg', 'jpeg', 'png']

def process_test_images_dir(dirname):
    results = []

    for image_name in os.listdir(dirname):
        matches = [image_name.endswith(format) for format in formats]
        if any(matches):
            image_path = os.path.join(dirname, image_name)
            img = try_read_image_from_path(image_path)
            res = ColorSolver(img, NUM_COLORS).solve()
            results.append([res, os.path.splitext(image_name)[0]])
    
    return results

def write_results(results, dirname):
    for res, image_name in results:
        compound_paths, colors, width, height = res
        f = open(os.path.join(dirname, f'{image_name}.svg'), 'w')
        f.write(create_markup(compound_paths, colors, width, height))
        f.close()

results = process_test_images_dir('test-images')
write_results(results, 'test-results')