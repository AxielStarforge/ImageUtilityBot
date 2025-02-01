import os
from io import BytesIO
import logging
from typing import Optional, Dict, Type, Tuple, List, Union
from enum import Enum
import cv2
import numpy as np
from rembg import remove
from PIL import Image
from aiogram import Bot, Dispatcher, types
from aiogram.types import BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageProcessing(StatesGroup):
    """States for the image processing workflow."""

    selecting_action = State()
    selecting_size = State()
    processing = State()


class ProcessingError(Exception):
    """Custom exception for image processing errors."""

    pass


class ImageSize(Enum):
    """Predefined image size options."""

    ORIGINAL = "original"
    SMALL = "720p"
    MEDIUM = "1080p"
    LARGE = "1440p"

    @classmethod
    def get_dimensions(cls, size: "ImageSize") -> Optional[Tuple[int, int]]:
        """Get the dimensions for a given size option."""
        dimensions = {
            cls.SMALL: (1280, 720),
            cls.MEDIUM: (1920, 1080),
            cls.LARGE: (2560, 1440),
        }
        return dimensions.get(size)


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
            # Save with format-specific settings
            if format_type == "png":
                cv2.imwrite(temp_path, image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            elif format_type in ["jpg", "jpeg"]:
                cv2.imwrite(temp_path, image, [cv2.IMWRITE_JPEG_QUALITY, 95])
            else:
                cv2.imwrite(temp_path, image)

            height, width = image.shape[:2]

            # Send the processed image
            async with open(temp_path, "rb") as f:
                await message.answer_photo(
                    BufferedInputFile(
                        await f.read(), filename=f"processed.{format_type}"
                    ),
                    caption=(
                        f"✅ {operation_name} completed successfully!\n"
                        f"Resolution: {width}x{height}"
                    ),
                )
        except Exception as e:
            raise ProcessingError(f"Failed to send processed image: {str(e)}")
        finally:
            await self.cleanup_files(temp_path)


class ImageConverter(ImageHandler):
    """Handles image format conversion with quality settings."""

    SUPPORTED_FORMATS = {"jpg", "jpeg", "png", "webp", "bmp", "tiff"}

    def __init__(self, format_type: str):
        self.format_type = format_type.lower()

    async def process(
        self, message: types.Message, file_path: str, target_size: ImageSize
    ) -> None:
        try:
            # Read image with alpha channel if present
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

            # Resize image if needed
            image = self.resize_image(image, target_size)

            # Send processed image
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


class BackgroundRemover(ImageHandler):
    """Handles background removal from images."""

    async def process(
        self, message: types.Message, file_path: str, target_size: ImageSize
    ) -> None:
        try:
            # Read image with PIL for rembg compatibility
            with Image.open(file_path) as img:
                # Remove background
                no_bg = remove(img)

                # Convert to numpy array for processing
                image = np.array(no_bg)

                # Resize if needed
                if target_size != ImageSize.ORIGINAL:
                    image = self.resize_image(image, target_size)

                # Send processed image
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


class UtilityMasterBot:
    """Main bot class handling image processing workflows."""

    HELP_MESSAGE = """
📚 Available commands:
/start - Begin interaction
/help - Show this help

Supported operations:
1. Convert to PNG
2. Convert to JPG
3. Convert to WEBP
4. Remove Background

Supported resolutions:
• Original size
• 720p (1280x720)
• 1080p (1920x1080)
• 1440p (2560x1440)
    """

    def __init__(self, bot_instance: Bot, dispatcher: Dispatcher):
        self.bot = bot_instance
        self.dp = dispatcher
        self.handlers: Dict[str, Type[ImageHandler]] = {
            "1": lambda: ImageConverter("png"),
            "2": lambda: ImageConverter("jpg"),
            "3": lambda: ImageConverter("webp"),
            "4": lambda: BackgroundRemover(),
        }
        self._configure_handlers()

    def _configure_handlers(self) -> None:
        """Configure bot command and message handlers."""
        self.dp.message.register(self.start, Command("start"))
        self.dp.message.register(self.help_command, Command("help"))
        self.dp.message.register(
            self.handle_image, lambda msg: msg.photo or msg.document
        )
        self.dp.message.register(
            self.handle_conversion_choice, ImageProcessing.selecting_action
        )
        self.dp.message.register(
            self.handle_size_choice, ImageProcessing.selecting_size
        )

    @staticmethod
    def create_format_keyboard() -> ReplyKeyboardMarkup:
        """Create a keyboard markup for operation selection."""
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=str(i))] for i in range(1, 5)],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    @staticmethod
    def create_size_keyboard() -> ReplyKeyboardMarkup:
        """Create a keyboard markup for size selection."""
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=size.value)] for size in ImageSize],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    async def start(self, message: types.Message) -> None:
        """Handle /start command."""
        await message.answer(
            "🖼️ Welcome to Image Utility Bot!\n"
            "Send me an image and choose an operation:\n"
            "• Convert between formats (PNG/JPG/WEBP)\n"
            "• Remove background\n"
            "• Resize to common resolutions"
        )

    async def help_command(self, message: types.Message) -> None:
        """Handle /help command."""
        await message.answer(self.HELP_MESSAGE)

    async def handle_image(self, message: types.Message, state: FSMContext) -> None:
        """Handle incoming images and documents."""
        try:
            if message.document:
                mime_type = message.document.mime_type
                if not mime_type.startswith("image/"):
                    await message.answer(
                        "❌ Please upload an image file (JPEG, PNG, WEBP, etc.)"
                    )
                    return

                format_type = mime_type.split("/")[-1].lower()
                if format_type not in ImageConverter.SUPPORTED_FORMATS:
                    await message.answer(f"❌ Unsupported format: {format_type}")
                    return

            wait_msg = await message.answer("⏳ Processing your image...")

            try:
                file = message.photo[-1] if message.photo else message.document
                file_path = await self.download_file(file)

                if not file_path:
                    raise ProcessingError("Failed to download file")

                await state.update_data(file_path=file_path)
                await message.answer(
                    "🔧 Choose operation:", reply_markup=self.create_format_keyboard()
                )
                await state.set_state(ImageProcessing.selecting_action)

            finally:
                await wait_msg.delete()

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            logger.error(error_msg)
            await message.answer(error_msg)

    async def handle_conversion_choice(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """Handle operation choice and prompt for size selection."""
        try:
            user_choice = message.text.strip()

            if user_choice not in self.handlers:
                await message.answer(
                    "❌ Invalid choice. Please select a number from the keyboard."
                )
                return

            await state.update_data(format_choice=user_choice)
            await message.answer(
                "📐 Choose output resolution:", reply_markup=self.create_size_keyboard()
            )
            await state.set_state(ImageProcessing.selecting_size)

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            logger.error(error_msg)
            await message.answer(error_msg)

    async def handle_size_choice(
        self, message: types.Message, state: FSMContext
    ) -> None:
        """Handle size selection and process the image."""
        try:
            size_choice = message.text.strip()
            try:
                target_size = next(
                    size for size in ImageSize if size.value == size_choice
                )
            except StopIteration:
                await message.answer(
                    "❌ Invalid size choice.Please select from the keyboard options."
                )
                return

            data = await state.get_data()
            file_path = data.get("file_path")
            format_choice = data.get("format_choice")

            if not all([file_path, format_choice]):
                raise ProcessingError("Missing required processing data")

            handler = self.handlers[format_choice]()
            await handler.process(message, file_path, target_size)

        except Exception as e:
            error_msg = f"❌ Processing Error: {str(e)}"
            logger.error(error_msg)
            await message.answer(error_msg)

        finally:
            await state.clear()
            # Cleanup the input file
            if "file_path" in data:
                await ImageHandler.cleanup_files(data["file_path"])

    async def download_file(
        self, file: types.PhotoSize | types.Document
    ) -> Optional[str]:
        """Download and save the uploaded file."""
        try:
            file_info = await self.bot.get_file(file.file_id)

            # Determine file extension
            ext = (
                "jpg"
                if isinstance(file, types.PhotoSize)
                else file.mime_type.split("/")[-1].replace("jpeg", "jpg")
            )

            file_path = f"downloads/{file.file_id}.{ext}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            await self.bot.download_file(file_info.file_path, file_path)
            logger.info(f"Successfully downloaded file to {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return None

    async def run(self) -> None:
        """Start the bot."""
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            raise
