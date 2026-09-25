# Midnight Strike regression fixture

User-supplied artwork for the color-deletion regression: small script lettering
and raccoon details must not grow thicker when the detected background is deleted.

`midnight_strike.png` is the lossless 1024 × 1024 processed RGBA image obtained with
`vectorizing.util.limit_size.limit_size` (Pillow 10.0.1, Lanczos) from the supplied
5001 × 5001 PNG. Its decoded pixels were verified identical to the production
resize. No extra quantization, filtering or JPEG encoding was applied.

The original is 17,664,245 bytes, exceeding the repository's 10 MB file limit.
Its SHA-256 is `345f11e8fa100cb04a44eeb8a053bdfea66d34391c8982086b5131e4d0d7d15f`.
The fixture SHA-256 is `7f00822a6c21ebac39a223000d7fbfaa6c9998024d00dd32eb96a90034eb9072`.

This is an input fixture, not a generated passing render baseline. Tests check
background deletion, zero opacity and assembled coverage across multiple palettes.
Foreground-to-foreground overlaps remain allowed; arbitrary color deletion is not
covered by this background-specific contract.

The input has partial alpha along its border. The existing quantizer classifies
it as an opaque output; background isolation must not change that classification.
