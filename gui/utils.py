import cv2
import numpy as np

import random
import time

random.seed(time.time())


def resize_cover(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize `image` to exactly (width, height) without distorting it.

    A plain cv2.resize to an arbitrary target size stretches non-uniformly
    whenever the target aspect ratio differs from the source's - a camera
    capture (4:3) squashed to fit a 16:9 box, say, comes out with everyone's
    face stretched wide. This scales up by the same factor in both
    directions (matching whichever dimension needs less enlarging) and then
    centre-crops the overflow, so proportions stay correct and only the
    edges of the picture are lost - the same "cover" behaviour as CSS
    background-size: cover.

    The output is always exactly (height, width) in shape, so callers that
    size other geometry (a display rect, a play field) from that shape see
    no change from a plain resize - only the pixel content differs.
    """
    source_height, source_width = image.shape[:2]
    scale = max(width / source_width, height / source_height)
    scaled_width = max(width, round(source_width * scale))
    scaled_height = max(height, round(source_height * scale))

    scaled = cv2.resize(image, (scaled_width, scaled_height))

    left = (scaled_width - width) // 2
    top = (scaled_height - height) // 2
    return scaled[top : top + height, left : left + width]


def random_bool_by_chance(chance: float) -> bool:
    """
    Generate a random boolean value based on a given chance, as chance increases, the likelihood of returning True increases.

    Args:
        chance (float): Chance of returning True (0.0 to 1.0).

    Returns:
        bool: Random boolean value.
    """
    return random.random() < chance


def biased_random_int(min_value, max_value, bias_range, bias_strength=2):
    """
    Generate a random integer between min_value and max_value with a bias towards a specific range.

    Args:
        min_value (int): The minimum value of the range.
        max_value (int): The maximum value of the range.
        bias_range (tuple): A tuple specifying the start and end of the biased range (inclusive).
        bias_strength (int): The strength of the bias. Higher values increase the likelihood of selecting
                             numbers in the bias_range. Default is 2.

    Returns:
        int: A random integer between min_value and max_value with a bias towards bias_range.
    """
    if not (
        min_value <= bias_range[0] <= max_value
        and min_value <= bias_range[1] <= max_value
    ):
        raise ValueError(
            "bias_range must be within the bounds of min_value and max_value."
        )

    weights = []
    for num in range(min_value, max_value + 1):
        # Assign higher weight to numbers within the bias range
        if bias_range[0] <= num <= bias_range[1]:
            weights.append(bias_strength)
        else:
            weights.append(1)

    # Generate a weighted random choice
    return random.choices(range(min_value, max_value + 1), weights=weights)[0]


# for _ in range(10):
#     # print(biased_random_int(0, 10, (1, 2), 5))
#     # print(random_bool_by_chance(0.9))
#     pass
