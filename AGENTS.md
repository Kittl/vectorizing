# Repository guide

Python 3.11 / Flask service that converts raster images to SVG using NumPy,
OpenCV, FAISS, scikit-image and Potrace. Requests can return raw SVG or upload it
to S3. Start with `README.md` for setup and usage.

## Code map

- `vectorizing/__init__.py`: app factory, request validation, cropping and API responses.
- `vectorizing/solvers/binary/`: binary masks and tracing.
- `vectorizing/solvers/color/`: quantization, cluster cleanup, ordered masks and tracing.
- `vectorizing/geometry/` and `vectorizing/svg/`: path conversion, bounds and SVG serialization.
- `vectorizing/util/`: image loading, color-mode normalization and size limits.
- `vectorizing/server/`: environment settings, S3, logging and timing.
- `vectorizing/tests/`: API contracts, image gallery and algorithm regressions.
- `scripts/`: local infrastructure, dependency generation and offline comparison/benchmark tools.

## Development and checks

Prefer Docker Compose; it supplies Moto S3 and needs no AWS account or `.env` file.
Run from the repository root:

```sh
docker compose up --build
pre-commit run --all-files
docker compose --profile testing run --build --rm test
```

For a focused test run:

```sh
docker compose --profile testing run --build --rm test \
  python -m pytest vectorizing/tests/test_color_bitmap_rims.py
```

- The API defaults to `http://localhost:8000` in Compose.
- Application source is copied into the image, not bind-mounted. Rebuild after edits.
- Use `docker compose down` to stop services you started; Moto data is discarded.
  Isolate project names and image tags when testing alongside other sessions/worktrees.
- Native execution needs the Python dependencies and system libraries from the
  Dockerfile/dev-container setup. Package imports require `PORT` and `S3_BUCKET`;
  integration tests also require a distinct `S3_TEST_BUCKET` and a local S3 endpoint.
- Preserve normal AWS behavior unless `AWS_ENDPOINT_URL` is explicitly configured.
  Use Moto for validation, not live buckets.
- CI runs the pre-commit hooks with Python 3.11 and the Compose test command.

## Output and behavior contracts

- Keep smooth anti-aliasing and transparent exteriors. Do not hide seams with SVG
  strokes or `shape-rendering="crispEdges"`, or reduce normal tracing quality.
- Color masks use bounded overlaps, not full underpainting. The current rim is
  two processed-image pixels; zoom enlarges it and very thin features may remain
  covered. Do not promise universally exact holes and seam-free rendering.
- Preserve palette/centroid ordering, dtypes and overflow behavior, connectivity,
  and independent mask storage when optimizing arrays. Rim conversion runs forward
  because the next mask must still be cumulative.
- Preserve public defaults, response/error shapes, return containers, SVG paint
  order and numeric formatting during refactors or performance work.
- Image readers currently wrap all loading failures, including interrupts, and URL
  downloads have no timeout. These are tested legacy contracts, not recommendations;
  change them deliberately with updated tests, never incidentally during lint cleanup.
- Comments and docstrings should explain behavior and invariants, not edit history.

## Regression evidence

- Add focused tests for changed behavior. Keep reference implementations independent
  of the optimized code they check.
- The gallery can auto-create missing PNG baselines. A newly seeded baseline does
  **not** prove equivalence; do not delete or replace baselines just to make tests pass.
- For output-preserving changes, capture before editing (or use a trusted baseline
  checkout), then compare SVG bytes, RGBA pixels, palettes, dimensions and bounds
  with `scripts/vectorization_outputs.py`. See the README for commands.
- For layer/geometry changes, check layer deletion, zero alpha and half opacity,
  transparent backgrounds and thin features, including `aftermath.png`. An assembled
  render alone cannot establish editability.
- Use `scripts/benchmark_vectorization.py` for measured performance claims. Retain
  raw samples, check equivalent outputs, and report runtime/hardware context. Its
  timing excludes input decoding, HTTP/S3 and rasterization; process peak RSS includes
  startup and warmups. Local results are not production or concurrent-load guarantees.

## Style, dependencies and artifacts

- Follow `.pre-commit-config.yaml` and `pyproject.toml`: Black, 88 columns, isort,
  annotations and NumPy-style docstrings. Avoid broad lint suppressions and keep
  correctness/security checks enabled. Passing lint is not a static-type-check claim.
- Prefer existing dependencies. Edit `requirements/prod.in` or `requirements/dev.in`,
  then use `scripts/compile_requirements.sh` and `scripts/compile_envs.sh` when dependency
  updates are needed. The latter requires the configured Conda `dev` environment.
  Keep system dependency setup consistent with `scripts/install_system_dependencies.sh`
  and the Dockerfile.
- Keep generated captures, benchmarks, investigations and scratch source under `.user/`
  or temporary directories, not tracked code. `.user/` is excluded from Git and Docker.
  Historical notes there may be stale; verify them against current source.
- Keep visual evidence local unless upload is explicitly requested. Never include
  credentials in reports or commits.

## Pull requests

Keep descriptions short and plain-language. Fetch `.github/pull_request_template.md`
from the `Kittl/.github` repository rather than inventing a replacement.
Leave owner attestations unchecked without explicit approval. Do not add agent/tool
badges. After addressing human review feedback, reply but leave the thread open
unless the user explicitly asks to resolve it; uncertain reviewer identity counts
as human.
