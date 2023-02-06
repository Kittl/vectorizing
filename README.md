## Kittl/Vectorizing
Utility to vectorize raster images.

## Usage
- `docker-compose up --build` to get started.
- `docker-compose up` to run the server.

You can then send `GET` requests to the server with the `?url=` query param. It should be a valid image url.

## Remarks
This utility is at a very early stage. For now, we only support single color output with transparent background. Color support might come in the future.

Adaptive thresholding is supported, but still not exposed as an option by the server.

Things to be done before `v1.0.0` is ready:
- See if thresholding methods can be easily improved
- Make sure output is consistent when using `RGBA` vs `RGB` images
- Set up github actions and staging / production environments
