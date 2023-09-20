import numpy as np
from PIL import Image
from io import BytesIO
from pathlib import Path
from cairosvg import svg2png

from vectorizing.tests.config import TESTS
from vectorizing.tests.testutil import get_markup, compute_img_difference, write_img_difference, RESULTS_FOLDER_PATH, MAX_IMAGE_DIFFERENCE, TMP_FOLDER_PATH

def test(client):
    """
    Tests all images inside /images directory using the TESTS object
    in config.py
    """

    results_path = Path(RESULTS_FOLDER_PATH)
    
    # Create results folder if non-existent
    if not results_path.exists():
        results_path.mkdir()

    # Cache test results to allow all tests to run
    diffs = []

    for img_name, options_list in TESTS.items():
        for options in options_list:
            id = options.get('id')
            output_name = f'{id}.png'
            
            # Vectorized SVG markup
            markup = get_markup(client, img_name, options)
            
            # Rasterized SVG
            png = svg2png(bytestring = markup)
            img = Image.open(BytesIO(png))
            
            # Store result if it doesn't exist yet
            results_output_path = Path(RESULTS_FOLDER_PATH / output_name)
            if not results_output_path.exists():
                img.save(results_output_path)

            else:
                # Difference between result and expected result
                difference = compute_img_difference(
                    img,
                    RESULTS_FOLDER_PATH / output_name
                )

                # Write image difference to diff_output
                if difference >= MAX_IMAGE_DIFFERENCE:
                    write_img_difference(
                        img, 
                        RESULTS_FOLDER_PATH / output_name, 
                        output_name
                    )

                diffs.append(difference)

    assert all([diff <= MAX_IMAGE_DIFFERENCE for diff in diffs])