import os
import cv2
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from abc import ABC, abstractmethod


class ImageProcessing(StatesGroup):
    selecting_action = State()
    processing = State()


class ImageHandler(ABC):
    """Abstract class for image processing operations."""

    @abstractmethod
    async def process(self, message: types.Message, file_path: str):
        pass


class ImageConverter(ImageHandler):
    """Handles image format conversion with quality settings."""

    def __init__(self, format_type: str):
        self.format_type = format_type.lower()

    async def process(self, message: types.Message, file_path: str):
        new_file_path = None
        try:
            image = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if image is None:
                raise ValueError("Unsupported file format or corrupted image")

            base_path = os.path.splitext(file_path)[0]
            new_file_path = f"{base_path}_converted.{self.format_type}"

            # Set format-specific parameters
            params = []
            if self.format_type == "jpg":
                params = [cv2.IMWRITE_JPEG_QUALITY, 95]
            elif self.format_type == "png":
                params = [cv2.IMWRITE_PNG_COMPRESSION, 5]

            if not cv2.imwrite(new_file_path, image, params):
                raise RuntimeError("Failed to save converted image")

            await message.answer_photo(
                FSInputFile(new_file_path),
                caption=f"Image converted to {self.format_type.upper()} successfully!",
            )

        except Exception as e:
            await message.answer(f"🔴 Conversion Error: {str(e)}")
        finally:
            # Clean up files
            for path in [file_path, new_file_path]:
                if path and os.path.exists(path):
                    os.remove(path)


class UtilityMasterBot:
    """Main bot class handling image processing workflows."""

    def __init__(self, bot_instance: Bot, dispatcher: Dispatcher):
        self.bot = bot_instance
        self.dp = dispatcher
        self._configure_handlers()

    def _configure_handlers(self):
        """Configure bot command and message handlers."""
        self.dp.message.register(self.start, Command("start"))
        self.dp.message.register(self.help_command, Command("help"))
        self.dp.message.register(
            self.handle_image, lambda msg: msg.photo or msg.document
        )
        self.dp.message.register(
            self.handle_conversion_choice, ImageProcessing.selecting_action
        )

    async def start(self, message: types.Message):
        """Handle /start command."""
        await message.answer(
            "🖼️ Welcome to Image Utility Bot!\n"
            "Send me an image and choose an operation:"
            "\n• Convert formats\n• Remove background"
        )

    async def help_command(self, message: types.Message):
        """Handle /help command."""
        await message.answer(
            "📚 Available commands:\n"
            "/start - Begin interaction\n"
            "/help - Show this help\n\n"
            "Supported operations:\n"
            "1. Convert between JPG/PNG\n"
            "2. Remove image background"
        )

    async def handle_image(self, message: types.Message, state: FSMContext):
        """Handle incoming images and documents."""
        try:
            # Validate document type
            if message.document and not message.document.mime_type.startswith("image/"):
                await message.answer("❌ Please upload an image file (JPEG, PNG, etc.)")
                return

            wait_msg = await message.answer("⏳ Processing your image...")
            file = message.photo[-1] if message.photo else message.document
            file_path = await self.download_file(file)

            if file_path:
                await state.update_data(file_path=file_path)
                await message.answer(
                    "🔧 Choose an operation: 1. Convert to JPG 2. Convert to PNG",
                    reply_markup=types.ReplyKeyboardMarkup(
                        keyboard=[
                            [types.KeyboardButton(text="1")],
                            [types.KeyboardButton(text="2")],
                            [types.KeyboardButton(text="3")],
                        ],
                        resize_keyboard=True,
                        one_time_keyboard=True,
                    ),
                )
                await state.set_state(ImageProcessing.selecting_action)

        except Exception as e:
            await message.answer(f"❌ Error: {str(e)}")
        finally:
            await wait_msg.delete()

    async def download_file(self, file: types.PhotoSize | types.Document):
        """Download and save the uploaded file with proper extension handling."""
        file_info = await self.bot.get_file(file.file_id)
        original_path = file_info.file_path

        # Determine file extension
        if isinstance(file, types.PhotoSize):
            ext = "jpg"
        else:
            filename = original_path.split("/")[-1]
            ext = filename.split(".")[-1] if "." in filename else "jpg"
            ext = ext[:4].lower()  # Sanitize extension

        file_path = f"downloads/{file.file_id}.{ext}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        await self.bot.download_file(original_path, file_path)
        return file_path

    async def handle_conversion_choice(self, message: types.Message, state: FSMContext):
        """Handle user's operation choice."""
        try:
            user_choice = message.text.strip()
            data = await state.get_data()
            file_path = data.get("file_path")

            handlers = {
                "1": ImageConverter("jpg"),
                "2": ImageConverter("png"),
                # "3": BackgroundRemover(),
            }

            if handler := handlers.get(user_choice):
                await handler.process(message, file_path)
            else:
                await message.answer("❌ Invalid choice. Please select 1, 2, or 3.")

        except Exception as e:
            await message.answer(f"❌ Processing Error: {str(e)}")
        finally:
            await state.clear()
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

    async def run(self):
        """Start the bot."""
        await self.dp.start_polling(self.bot)
