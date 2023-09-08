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