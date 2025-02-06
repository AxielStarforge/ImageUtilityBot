import numpy as np
import logging
from PIL import Image
from rembg import remove
from aiogram import types
from .image_handler import ImageHandler
from enums.image_size import ImageSize


logger = logging.getLogger(__name__)


class BackgroundRemover(ImageHandler):
    """Handles background removal from images."""

    async def process(
        self, message: types.Message, file_path: str, target_size: ImageSize
    ) -> None:
        try:
            with Image.open(file_path) as img:
                no_bg = remove(img)
                image = np.array(no_bg)
                if target_size != ImageSize.ORIGINAL:
                    image = self.resize_image(image, target_size)
                await self.send_processed_image(
                    message,
                    image,
                    "png",  # Always use PNG for transparency
                    "Background removal",
                )
        except Exception as e:
            error_msg = f"🔴 Background Removal Error: {str(e)}"
            logger.error(error_msg)
            await message.answer(error_msg)
