import cv2
import numpy as np

import random
import time

random.seed(time.time())


def img_with_rounded_corners(image: np.ndarray, r: int, t: int, c: tuple) -> np.ndarray:
    """
    Draw a rectangle with rounded corners on an image.

    Args:
        image (np.ndarray): Image to draw on.
        r (int): Radius of the rounded corners.
        t (int): Thickness of the rectangle.
        c (tuple): Color of the rectangle.

    Returns:
        np.ndarray: Image with the drawn rectangle.
    """

    c += (255,)

    h, w = image.shape[:2]

    # Create new image (three-channel hardcoded here...)
    new_image = np.ones((h + 2 * t, w + 2 * t, 4), np.uint8) * 255
    new_image[:, :, 3] = 0

    # Draw four rounded corners
    new_image = cv2.ellipse(
        new_image, (int(r + t / 2), int(r + t / 2)), (r, r), 180, 0, 90, c, t
    )
    new_image = cv2.ellipse(
        new_image,
        (int(w - r + 3 * t / 2 - 1), int(r + t / 2)),
        (r, r),
        270,
        0,
        90,
        c,
        t,
    )
    new_image = cv2.ellipse(
        new_image,
        (int(r + t / 2), int(h - r + 3 * t / 2 - 1)),
        (r, r),
        90,
        0,
        90,
        c,
        t,
    )
    new_image = cv2.ellipse(
        new_image,
        (int(w - r + 3 * t / 2 - 1), int(h - r + 3 * t / 2 - 1)),
        (r, r),
        0,
        0,
        90,
        c,
        t,
    )

    # Draw four edges
    new_image = cv2.line(
        new_image,
        (int(r + t / 2), int(t / 2)),
        (int(w - r + 3 * t / 2 - 1), int(t / 2)),
        c,
        t,
    )
    new_image = cv2.line(
        new_image,
        (int(t / 2), int(r + t / 2)),
        (int(t / 2), int(h - r + 3 * t / 2)),
        c,
        t,
    )
    new_image = cv2.line(
        new_image,
        (int(r + t / 2), int(h + 3 * t / 2)),
        (int(w - r + 3 * t / 2 - 1), int(h + 3 * t / 2)),
        c,
        t,
    )
    new_image = cv2.line(
        new_image,
        (int(w + 3 * t / 2), int(r + t / 2)),
        (int(w + 3 * t / 2), int(h - r + 3 * t / 2)),
        c,
        t,
    )

    # Generate masks for proper blending
    mask = new_image[:, :, 3].copy()
    mask = cv2.floodFill(mask, None, (int(w / 2 + t), int(h / 2 + t)), 128)[1]
    mask[mask != 128] = 0
    mask[mask == 128] = 1
    mask = np.stack((mask, mask, mask), axis=2)

    # Blend images
    temp = np.zeros_like(new_image[:, :, :3])
    temp[(t - 1) : (h + t - 1), (t - 1) : (w + t - 1)] = image.copy()
    new_image[:, :, :3] = new_image[:, :, :3] * (1 - mask) + temp * mask

    # Set proper alpha channel in new image
    temp = new_image[:, :, 3].copy()
    new_image[:, :, 3] = cv2.floodFill(
        temp, None, (int(w / 2 + t), int(h / 2 + t)), 255
    )[1]

    return new_image


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
