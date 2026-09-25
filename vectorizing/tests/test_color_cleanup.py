"""Area-only cleanup preserves thin connected regions and transparent counters."""

import numpy as np
import pytest

from vectorizing.solvers.color.quantize import clean_components
from vectorizing.tests.color_reference import reference_clean_components


@pytest.mark.parametrize("count", [1, 2, 6, 16, 64, 65])
@pytest.mark.parametrize("transparent", [False, True])
@pytest.mark.parametrize("strided", [False, True])
@pytest.mark.parametrize("seed", range(3))
def test_cleanup_matches_per_color_reference(
    count: int,
    transparent: bool,
    strided: bool,
    seed: int,
) -> None:
    """Match a separate CCL implementation without changing input storage/dtype."""
    rng = np.random.default_rng(seed)
    labels = rng.integers(0, count, (39, 47), dtype=np.uint16)
    labels[:5] = 0  # Ensure a survivor even in high-color random cases.
    if strided:
        labels = labels[::2, ::2]
    background = (labels == 0).astype(np.uint8) if transparent else None
    original = labels.copy()
    labels.setflags(write=False)
    actual = clean_components(labels, background)
    np.testing.assert_array_equal(
        actual,
        reference_clean_components(labels, background),
    )
    np.testing.assert_array_equal(labels, original)
    assert actual.dtype == labels.dtype


@pytest.mark.parametrize("area", [1, 7, 8, 9, 20])
def test_thin_components_use_area_not_interior_ratio(area: int) -> None:
    """Keep one-pixel-wide features of at least eight pixels, including the cutoff."""
    labels = np.zeros((25, 25), dtype=np.uint16)
    labels[10, 2 : 2 + area] = 1
    expected = labels if area >= 8 else np.zeros_like(labels)
    np.testing.assert_array_equal(clean_components(labels, None), expected)


def test_diagonals_form_one_component() -> None:
    """Eight corner-connected pixels survive even though none has an interior."""
    labels = np.zeros((16, 16), dtype=np.uint16)
    indices = np.arange(3, 11)
    labels[indices, indices] = 1
    np.testing.assert_array_equal(clean_components(labels, None), labels)


def test_small_transparent_counter_is_protected() -> None:
    """Never remove a background hole, even when it is smaller than the area cutoff."""
    labels = np.ones((16, 16), dtype=np.uint16)
    labels[8, 8] = 0
    background = (labels == 0).astype(np.uint8)
    np.testing.assert_array_equal(clean_components(labels, background), labels)


@pytest.mark.parametrize("area", [1, 4, 7, 8])
def test_enclosed_opaque_counter_survives(area: int) -> None:
    """Protect background-colored counters even below the usual area cutoff."""
    labels = np.zeros((16, 16), dtype=np.uint16)
    labels[3:13, 3:13] = 1
    labels[7, 4 : 4 + area] = 0
    np.testing.assert_array_equal(clean_components(labels, None), labels)


@pytest.mark.parametrize("shape", [(1, 1), (1, 7), (7, 1), (4, 4)])
def test_no_survivors_retains_original_labels(shape: tuple[int, int]) -> None:
    """Do not feed an all-foreground distance transform when every region is tiny."""
    labels = np.arange(np.prod(shape), dtype=np.uint16).reshape(shape)
    np.testing.assert_array_equal(clean_components(labels, None), labels)


def test_background_selection_ignores_tiny_perimeter_components() -> None:
    """Discard border noise rather than mistaking its frequent color for background."""
    labels = np.ones((20, 20), dtype=np.uint16)
    labels[0, ::2] = labels[-1, ::2] = 0
    labels[::2, 0] = labels[::2, -1] = 0
    np.testing.assert_array_equal(clean_components(labels, None), 1)


@pytest.mark.parametrize("shape", [(1, 20), (20, 1)])
def test_background_selection_on_narrow_images(shape: tuple[int, int]) -> None:
    """Count each perimeter pixel once on a single row or column."""
    labels = np.array([1] + [2] * 8 + [1] * 11, dtype=np.uint16).reshape(shape)
    np.testing.assert_array_equal(
        clean_components(labels, None),
        reference_clean_components(labels, None),
    )


def test_small_island_can_refill_from_transparent_background() -> None:
    """Remove tiny opaque specks without painting over transparent pixels."""
    labels = np.zeros((12, 12), dtype=np.uint16)
    labels[5, 5] = 1
    background = (labels == 0).astype(np.uint8)
    np.testing.assert_array_equal(clean_components(labels, background), 0)
