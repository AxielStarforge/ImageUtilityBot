from enum import Enum
from typing import Optional, Tuple


class ImageSize(Enum):
    """Predefined image size options."""

    ORIGINAL = "original"
    SMALL = "720p"
    MEDIUM = "1080p"
    LARGE = "1440p"
    HUGE = "5000"

    @classmethod
    def get_dimensions(cls, size: "ImageSize") -> Optional[Tuple[int, int]]:
        dimensions = {
            cls.SMALL: (1280, 720),
            cls.MEDIUM: (1920, 1080),
            cls.LARGE: (2560, 1440),
            cls.HUGE: (5000, 5000)
        }
        return dimensions.get(size)
