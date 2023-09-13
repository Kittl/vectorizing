## Kittl/Vectorizing

[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Kittl/vectorizing)

Utility to vectorize raster images :rocket:

## Local development

#### **First time run**

Open this repository in the dev container:
1. Install [`dev container`](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension in vscode
2. At the top of the repo click the `Open in dev container` badge, or, in vscode press `cmd+shift+p` and search for the command: `Dev Containers: Open Folder in Container`
3. The dev container has already installed all necessary tools: `conda`, `black`, `flake8`, `pre-commit`, `AWS CLI`, `Act`

The first time the execution can take few minutes, as it is pulling the dev container docker image, and installing Vectorizing system and python dependencies inside of it.

#### **Development workflow**

1. There is a debug configuration named `Vectorizing` setup, press `F5` to run. It will start the flask application in development mode, listening on `localhost:8080`. If neeed, this can be changed in the [debug configuration file](.vscode/launch.json).

2. If you want to execute any python command that uses `Vectorizing` packages, you need to first activate the conda environment in every new terminal you open, by running: `conda activate dev`

3. If you want to add or remove dependencies python dependencies, add / remove the corresponding package from either [`requirements/prod.in`](requirements/prod.in) or [`requirements/dev.in`](requirements/dev.in). Then run, from the root of the repo:

	```bash
	bash scripts/compile_requirements.sh
	bash scripts/compile_envs.sh
	```

This will compile dependencies and environments, ensuring a consistent development workflow and deployment.

## Server

The server has a single endpoint that receives `POST` requests.
The request format is the following:

```typescript
{
	url: string, // Image URL
	solver: number, // Solver. 0 -> Binary, 1 -> Color
	color_count: number, // Number of colors (if applicable)
	raw: boolean // If true, plain return plain SVG markup
}
```

A typical response would be

```typescript
	success: boolean, // Whether the request was successful
	objectId: string, // The object id in the S3 bucket
		info: {
			// Bounds of the computed vectors
			bounds: {
				left: number,
				top: number,
				bottom: number,
				right: number,
				width: number,
				height: number
			},
	image_width: number, // Image width
	image_height: number // Image height
}
```

Or, if `raw = true` was supplied, just plain SVG markup

## Testing

### Required setup
If needed, update the `S3_TEST_BUCKET` environment variable in your `.env` file. You should have read + write access to it.

Tests work on rasterized versions of vectorized markup. i.e
1. Images are vectorized
2. SVG markup is then rasterized

They should primarily focus on making sure that
- Random requests with different input data don't crash the server
- Changes in results don't go unnoticed

To run tests, you can run

```
python -m pytest vectorizing/tests/test.py
```

### Adding new tests
To add a new test:
- Place the image you want to be tested inside `vectorizing/tests/images`
- Add an entry to the `TEST` object in `vectorizing/tests/config.py` in the following form:

   ```python
	# New object entry
	'[name_of_image]': [
		# Here, a list of all tests to be ran
		{
			'id': '[test_case_id]' # Test case id, used to generate file names
			'solver': 0, # Solver to use
		},
		{
			'id': '[test_case_id_2]'
			'solver': 1,
			'color_count': # Amount of colors
		}
	]
   ```
- Run the tests
- Verify the output in `vectorizing/testing/results`. A new image of the test result should have been placed there. If it looks correct, keep it. It will be used as a baseline for subsequent test runs.

## Failing tests
- When any of the test cases fail, an entry will be placed in `vectorizing/tests/diff_output` highlighting the parts of the test result that are too far apart from the baseline entries.

