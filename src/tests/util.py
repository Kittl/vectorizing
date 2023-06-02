import os
from pathlib import Path
from image_read import try_read_image_from_path
from solvers.color_solver import solve as color_solve, remove_edge_artifacts
from misc.kmeans import optimal_kmeans
from PIL import Image
from solvers.preprocess_input import perpare_image
from solvers.color.solver import ColorSolver

formats = ['jpg', 'jpeg', 'png']

def process_image_directory(images_dirname):
    results = []

    for image_name in os.listdir(images_dirname):
        matches = [image_name.endswith(format) for format in formats]
        if any(matches):
            image_path = os.path.join(images_dirname, image_name)
            img = try_read_image_from_path(image_path)
            res = ColorSolver(img).solve()
            results.append([res, os.path.splitext(image_name)[0]])
    return results
    
def dump_results_in_directory(results, target_directory):
    for res, image_name in results:
        path = os.path.join(target_directory, image_name)
        Path(path).mkdir(exist_ok = True)

        for filename in os.listdir(path):
            os.remove(os.path.join(path, filename))

        markup, posterized, posterized_before = res

        f = open(os.path.join(path, f'{image_name}.svg'), 'w')
        f.write(markup)
        f.close()

        posterized = Image.fromarray(posterized)
        posterized.save(os.path.join(path, f'{image_name}.png'))

        posterized_before = Image.fromarray(posterized_before)
        posterized_before.save(os.path.join(path, f'{image_name}_before.png'))