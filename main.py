import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from bot.image_utility_bot import ImageUtilityBot  

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    try:
        TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not TOKEN:
            raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

        # Initialize bot with your token
        bot = Bot(token=TOKEN)

        # Create dispatcher with memory storage
        dp = Dispatcher(storage=MemoryStorage())

        # Create downloads directory
        os.makedirs("downloads", exist_ok=True)

        # Initialize and run the bot
        utility_bot = ImageUtilityBot(bot, dp)
        logger.info("Starting bot...")
        await utility_bot.run()

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise
    finally:
        # Cleanup on shutdown
        if "bot" in locals():
            await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
