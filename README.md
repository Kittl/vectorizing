## Kittl/Vectorizing

Utility to vectorize raster images :rocket:

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