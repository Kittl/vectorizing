from tests.util import process_image_directory, dump_results_in_directory
results = process_image_directory('src/tests/custom/images')
dump_results_in_directory(results, 'src/tests/custom/results')