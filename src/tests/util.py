import os, shutil
from pathlib import Path
from image_read import try_read_image_from_path
from solvers.color_solver import solve as color_solve, remove_edge_artifacts
from misc.kmeans import optimal_kmeans
from PIL import Image
from solvers.preprocess_input import perpare_image

formats = ['jpg', 'jpeg', 'png']

def process_image_directory(images_dirname):
    results = []

    for image_name in os.listdir(images_dirname):
        matches = [image_name.endswith(format) for format in formats]
        if any(matches):
            image_path = os.path.join(images_dirname, image_name)
            img = try_read_image_from_path(image_path)
            opt_k, markup = color_solve(img, { 'color_count': 12 })
            img = perpare_image(img)
            _, labels, centers = optimal_kmeans(img, 12)
            labels_a, centers_a = remove_edge_artifacts(img, labels, centers)
            posterized = centers[labels]
            posterized_a = centers_a[labels_a]
            results.append([opt_k, markup, posterized, posterized_a, os.path.splitext(image_name)[0]])
    return results
    
def dump_results_in_directory(results, target_directory):
    for opt_k, markup, posterized, posterized_a, image_name in results:
        path = os.path.join(target_directory, image_name)
        Path(path).mkdir(exist_ok = True)

        for filename in os.listdir(path):
            os.remove(os.path.join(path, filename))

        #Markup
        f = open(os.path.join(path, f'result_{opt_k}.svg'), 'w')
        f.write(markup)
        f.close()

        #Posterized
        img = Image.fromarray(posterized)
        img.save(os.path.join(path, 'posterized.png'))
        
        #Posterized-After
        img = Image.fromarray(posterized_a)
        img.save(os.path.join(path, 'posterized-after.png'))