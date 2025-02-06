import cv2
import logging
from aiogram import types
from .image_handler import ImageHandler
from enum.image_size import ImageSize
from error.processing_error import ProcessingError

logger = logging.getLogger(__name__)


class ImageConverter(ImageHandler):
    """Handles image format conversion with quality settings."""

    SUPPORTED_FORMATS = {"jpg", "jpeg", "png", "webp", "bmp", "tiff"}

    def __init__(self, format_type: str):
        self.format_type = format_type.lower()

    async def process(
        self, message: types.Message, file_path: str, target_size: ImageSize
    ) -> None:
        try:
            image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                raise ProcessingError("Failed to read image file")

            # Handle alpha channel
            if self.format_type == "png" and image.shape[-1] == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
            elif (
                self.format_type != "png"
                and len(image.shape) > 2
                and image.shape[-1] == 4
            ):
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

            image = self.resize_image(image, target_size)

            await self.send_processed_image(
                message,
                image,
                self.format_type,
                f"Conversion to {self.format_type.upper()}",
            )

        except Exception as e:
            error_msg = f"🔴 Conversion Error: {str(e)}"
            logger.error(error_msg)
            await message.answer(error_msg)
