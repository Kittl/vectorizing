def truncate(number):
    """
    Truncates a number to two decimal places.
    We use this to limit the amount of decimal places used
    in the final generated SVG markup (reduces file sizes).

        Parameters:
            number: The number to truncate.

        Returns:
            The truncated number.
    """
    return "{:.2f}".format(number)


def to_SVG_color_string(color):
    """
    Converts a color (represented as a tuple) to a valid
    SVG color string.

        Parameters:
            color: The input color.

        Returns:
            The SVG color string.

        Example:
            to_SVG_color_string([20, 30, 40]) => rgb(20, 30, 40)
            to_SVG_color_string([20, 30, 40, 0.5]) => rgba(20, 30, 40, 0.5)

    """
    func = "rgb" if len(color) == 3 else "rgba"
    tuple = "".join(
        [
            f"{item}," if i != len(color) - 1 else f"{item}"
            for i, item in enumerate(color)
        ]
    )
    return f"{func}({tuple})"


def generate_SVG_markup(compound_paths, colors, width, height):
    """
    Generates SVG markup from a list of compound paths,
    their respective colors, and the document dimensions.

        Parameters:
            compound_paths: The compound path list (SKPath).
            colors: Each compound path's color.
            width: The width of the document.
            height: The height of the document.

        Returns:
            The SVG markup.

        Note:
            compound paths are assumed to be made out of
            only lines and cubic beziers.
    """
    paths_markup = []

    for compound_path, color in zip(compound_paths, colors):
        segments = list(compound_path.segments)
        if not len(segments):
            continue

        d = ""
        for segment in segments:
            command = segment[0]
            if command == "moveTo":
                x = segment[1][0][0]
                y = segment[1][0][1]
                d += f"M {truncate(x)} {truncate(y)} "
            if command == "lineTo":
                x = segment[1][0][0]
                y = segment[1][0][1]
                d += f"L {truncate(x)} {truncate(y)} "
            if command == "curveTo":
                d += (
                    "C" + f"{truncate(segment[1][0][0])},{truncate(segment[1][0][1])} "
                    f"{truncate(segment[1][1][0])},{truncate(segment[1][1][1])} "
                    f"{truncate(segment[1][2][0])},{truncate(segment[1][2][1])} "
                )
            if command == "closePath":
                d += "Z"

        path_markup = f'<path d="{d}" fill="{to_SVG_color_string(color)}" />'
        paths_markup.append(path_markup)

    paths_markup = "\n".join(paths_markup)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        f"<g>\n{paths_markup}\n</g>\n"
        f"</svg>"
    )
