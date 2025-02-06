import os
import logging
from typing import Dict, Type, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from image.image_processing import ImageProcessing
from image.image_handler import ImageHandler
from image.image_converter import ImageConverter
from image.background_remover import BackgroundRemover
from enum.image_size import ImageSize
from error.processing_error import ProcessingError

logger = logging.getLogger(__name__)


class ImageUtilityBot:
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

    # Command handlers
    def _configure_handlers(self) -> None:
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
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=str(i))] for i in range(1, 5)],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    @staticmethod
    def create_size_keyboard() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=size.value)] for size in ImageSize],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    # START [/start]
    async def start(self, message: types.Message) -> None:
        await message.answer(
            "🖼️ Welcome to Image Utility Bot!\n"
            "Send me an image and choose an operation:\n"
            "• Convert between formats (PNG/JPG/WEBP)\n"
            "• Remove background\n"
            "• Resize to common resolutions"
        )

    # HELP [/help]
    async def help_command(self, message: types.Message) -> None:
        await message.answer(self.HELP_MESSAGE)

    # Prompt user for image upload and deliver image processing options
    async def handle_image(self, message: types.Message, state: FSMContext) -> None:
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

    # Convert image formats
    async def handle_conversion_choice(
        self, message: types.Message, state: FSMContext
    ) -> None:
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

    # Present image size options and handle image resizing
    async def handle_size_choice(
        self, message: types.Message, state: FSMContext
    ) -> None:
        data = await state.get_data()
        try:
            size_choice = message.text.strip()
            try:
                target_size = next(
                    size for size in ImageSize if size.value == size_choice
                )
            except StopIteration:
                await message.answer(
                    "❌ Invalid size choice. Please select from the keyboard options."
                )
                return

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
            if "file_path" in data:
                await ImageHandler.cleanup_files(data["file_path"])

    # Return processed image to user to download
    async def download_file(
        self, file: types.PhotoSize | types.Document
    ) -> Optional[str]:
        try:
            file_info = await self.bot.get_file(file.file_id)
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

    # RUN
    async def run(self) -> None:
        try:
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            raise
