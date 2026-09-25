## Kittl/Vectorizing

[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/Kittl/vectorizing)

Utility to vectorize raster images :rocket:

## Local development

### Docker Compose (recommended)

Docker Compose runs the application with a local [Moto](https://github.com/getmoto/moto) S3 server. No AWS account, credentials, bucket, or `.env` file is required.

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`. Stop both services with `docker compose down`; Moto's data is intentionally discarded.

#### **First time run (Dev Container)**

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

4. If you want to add or remove **system** dependencies, update the script: [`scripts/install_system_dependencies.sh`](scripts/install_system_dependencies.sh). This is used both in CI and at dev container creation, to keep them consistent.

## Linting and formatting

To perform linting and formatting, run from the root of the repo:

```
pre-commit run --all-files
```

The first execution might take a bit longer, as it will set up the virtual environment
where the linter and the formatter will run.

## Output comparisons and benchmarks

These developer commands use local fixtures and need no AWS credentials or Moto.
Run them in the dev container or an environment with `requirements/dev.txt` and
its system libraries installed. They do not change application code or dependencies.

Capture each version into a different directory, then compare:

```bash
python scripts/vectorization_outputs.py capture .user/before --source-root /path/to/baseline
python scripts/vectorization_outputs.py capture .user/after
python scripts/vectorization_outputs.py compare .user/before .user/after
python scripts/benchmark_vectorization.py --output .user/benchmark.json --case aftermath-16
```

- Repeat `--case` to select fixtures; `--help` lists them. The default is all 15 cases.
- Comparison checks SVG bytes, decoded RGBA pixels, colors, dimensions, bounds and input identity. Exit codes: `0` equal, `1` changed, `2` invalid/incomplete artifacts. Nonempty output directories and existing benchmark reports are never overwritten.
- Benchmark timing covers the solver, SVG serialization and bounds, not file decoding, HTTP/S3 or rasterization. Each sample uses a fresh process; peak RSS includes imports, input preparation, warmups and output checks. Linux and macOS memory units are normalized to MiB.
- Add `--baseline-root /path/to/baseline` to benchmark two trusted checkouts in alternating order, with exact-output checks. `--repeats` defaults to 3 and `--warmups` to 1 per process. Output mismatches exit `1` but still save the report; timings have no pass/fail threshold.
- Reports include runtime/source fingerprints and raw samples. `--label` can record commit IDs. Checkouts share the installed dependencies; this is not a dependency-isolated or production/concurrency benchmark. Use only trusted source roots.

For Docker, build the current scripts and mount only the output directory:

```bash
mkdir -p .user
docker build -t vectorizing:tools .
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/.user:/results" vectorizing:tools \
  python scripts/vectorization_outputs.py capture /results/candidate
```

A separate baseline checkout must also be mounted when using `--source-root` or
`--baseline-root`. Generated artifacts under `.user/` are excluded from Git and Docker builds.

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
{
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

Color processing uses a gentle 3-pixel bilateral filter and removes only connected
components smaller than eight processed-image pixels, rather than rejecting thin
regions based on their shape. Transparent pixels are protected; on opaque images,
the most common surviving perimeter color is also protected to retain small
background-colored letter counters. This can retain extra small specks of that
color. Tracing retains small paths and uses a curve optimization tolerance of 0.5.
The existing 1,048,576-pixel area cap, default of six
colors and supported range of 2–64 colors are unchanged. Color paths touching the
canvas are extended before tracing and clipped back to the image so corners remain
covered and returned bounds do not include the padding. If Skia rejects a canvas
clip, that layer is retraced without padding and a warning is logged. Recovery
constrains any outlying curve control points to the canvas. It keeps smooth editable
vectors instead of failing the request, but can adjust curves near the canvas and
round corners inward, reducing edge coverage on the affected layer.

SVGs use compact absolute/relative commands on an integer hundredth-pixel grid,
inside a `scale(.01)` group. This preserves the previous two-decimal coordinate
rounding, viewport, paint order and opacity without raster images or SVG strokes.
Binary tracing is unchanged, but both solvers use the compact serializer. Equivalent
geometry can produce small renderer-specific antialiasing differences; exact pixel
identity across viewers and zoom levels is not guaranteed. Potrace and pypotrace
remain dependencies under their existing GPL licenses.

Color layers have cutouts with a small overlap along shared edges to hide seams.
The overlap is two pixels in the resized image before tracing, not screen pixels.
Hiding a color can expose this rim; very thin features may remain covered, and
zooming in makes the rim larger. No SVG strokes are added.

Background deletion has a conservative exception: if the existing quantizer treats
an image as opaque, its entire processed perimeter has one uniquely identifiable
palette color, and that color is the last/frontmost used layer, the solver trims
its hidden foreground overlaps and paints a bounded background first. This keeps
background deletion from fattening the artwork while retaining smooth tracing.
The background still has only a two-pixel rim, not a full-canvas underpainting.
Already-first backgrounds, intermediate background layers, ambiguous borders and
outputs with detected transparency stay unchanged. This uses the existing alpha
classification, not a new requirement that every input alpha value be 255.
If an isolation subtraction or its new background clip fails, the complete original
layer set is retained with a warning. Other foreground-color deletions can still
expose their existing overlaps. Paint order and some edge pixels change for
qualifying images; target-editor import/edit/export should be checked before release.

## Testing

Tests work on rasterized versions of vectorized markup. i.e
1. Images are vectorized
2. SVG markup is then rasterized

They should primarily focus on making sure that
- Random requests with different input data don't crash the server
- Changes in results don't go unnoticed

To run tests against the local Moto service, run:

```
docker compose --profile testing run --build --rm test
```

Tests are split into `test_*.py` files in `vectorizing/tests`. Compose and CI
run them all. `color_reference.py` keeps independent centroid, bitmap and area-cleanup
oracles. The color acceptance tests also check the approved Aftermath geometry,
Bubble Whirl's lettering counters, alpha behavior and compact SVG coordinates.

When running pytest outside Compose, configure the AWS variables for an S3-compatible service first.

### Required setup

The recommended Docker Compose test command uses Moto and requires no AWS access. When running tests outside Compose, configure `S3_TEST_BUCKET` and the standard AWS variables for the S3-compatible service you want to use.

### Adding new tests
To add a new test:
- Place the image you want to be tested inside `vectorizing/tests/images`
- Add an entry to the `TESTS` object in `vectorizing/tests/config.py` in the following form:

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
- Verify the output in `vectorizing/tests/results`. A new image of the test result should have been placed there. If it looks correct, keep it. It will be used as a baseline for subsequent test runs.

## Failing tests
- When any of the test cases fail, an entry will be placed in `vectorizing/tests/diff_output` highlighting the parts of the test result that are too far apart from the baseline entries.

