## Kittl/Vectorizing

Utility to vectorize raster images :rocket:

## Local development

1. Install python development tools:
	- Open this repository in the dev container:
		- Install [`dev container`](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension in vscode
		- In vscode press `cmd+shift+p` and search for the command: `Open folder in container`
		- The dev container has already installed all necessary tools: `conda`, `black`, `flake8`, `pre-commit`, `AWS CLI`, `Act`
	- Install manually:
		- [Conda](https://docs.conda.io/projects/miniconda/en/latest/miniconda-install.html)

2. Install system dependencies for pypotrace:

	```bash
	sudo apt-get update
	sudo apt-get install build-essential python-dev libagg-dev libpotrace-dev pkg-config
	```

3. Create the conda development environment and activate it

	```bash
	conda env create -n dev -f envs/dev.yaml
	conda activate dev
	```

4. If you want to add or remove dependencies, add / remove the corresponding package from either [`requirements/prod.in`](requirements/prod.in) or [`requirements/dev.in`](requirements/dev.in). Then run, from the root of the repo:

	```bash
	bash scripts/compile_requirements.sh
	bash scripts/compile_envs.sh
	```

## Usage

-  `docker compose up --build` to start the server.

-  `docker compose run --build test` to run manual tests.

Manual tests are just visual tests. Images located in `test-images` are processed by the solver(s) and the results placed in `test-results`. This is probably temporary until we set up unit tests.

## Server

The server has a single endpoint (/) that receives `POST` requests.
The request format is the following:

```
{
	url: a valid url to read the image from,
	solver: 0 for black and white, 1 for color,
	color_count: if solver = 1, amount of colors to use,
	raw: if true, return only the SVG markup
}
```

A typical response would be

```
	success: whether the request was successful,
	objectId: the id used to upload the SVG to the S3 bucket,
		info: {
			bounds: {
				left: number,
				top: number,
				bottom: number,
				right: number,
				width: number,
				height: number
			},
	image_width: the image width,
	image_height: the image height
}
```

Or, if `raw = true` was supplied, just plain SVG markup

## Remarks
This utility is at an early stage. There are improvements to be made. Mainly regarding image quantization.

TODO

- Set up github actions

- Set up unit tests