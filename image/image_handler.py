import os
import cv2
import numpy as np
import logging
from abc import ABC, abstractmethod
from aiogram import types
from aiogram.types import BufferedInputFile
from enums.image_size import ImageSize
from error.processing_error import ProcessingError

logger = logging.getLogger(__name__)


class ImageHandler(ABC):
    """Abstract base class for image processing operations."""

    @abstractmethod
    async def process(
        self, message: types.Message, file_path: str, target_size: ImageSize
    ) -> None:
        """Process the image and send the result back to the user."""
        pass

    @staticmethod
    async def cleanup_files(*file_paths: str) -> None:
        """Safely clean up temporary files."""
        for path in file_paths:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    logger.info(f"Cleaned up file: {path}")
                except Exception as e:
                    logger.error(f"Failed to clean up {path}: {e}")

    @staticmethod
    def resize_image(image: np.ndarray, target_size: ImageSize) -> np.ndarray:
        """Resize image while maintaining aspect ratio and quality."""
        if target_size == ImageSize.ORIGINAL:
            return image

        target_dims = ImageSize.get_dimensions(target_size)
        if not target_dims:
            return image

        target_width, target_height = target_dims
        height, width = image.shape[:2]
        aspect = width / height
        if width > height:
            new_width = min(width, target_width)
            new_height = int(new_width / aspect)
        else:
            new_height = min(height, target_height)
            new_width = int(new_height * aspect)

        return cv2.resize(
            image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4
        )

    async def send_processed_image(
        self,
        message: types.Message,
        image: np.ndarray,
        format_type: str,
        operation_name: str,
    ) -> None:
        """Send processed image back to user with proper format and metadata."""
        temp_path = f"downloads/temp_output.{format_type}"
        try:
            if format_type == "png":
                cv2.imwrite(temp_path, image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            elif format_type in ["jpg", "jpeg"]:
                cv2.imwrite(temp_path, image, [cv2.IMWRITE_JPEG_QUALITY, 95])
            else:
                cv2.imwrite(temp_path, image)

            height, width = image.shape[:2]

            async with open(temp_path, "rb") as f:
                await message.answer_photo(
                    BufferedInputFile(
                        await f.read(), filename=f"processed.{format_type}"
                    ),
                    caption=f"✅ {operation_name} completed successfully!\nResolution: {width}x{height}",
                )
        except Exception as e:
            raise ProcessingError(f"Failed to send processed image: {str(e)}")
        finally:
            await self.cleanup_files(temp_path)
