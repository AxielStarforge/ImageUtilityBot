import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from bot.utility_master_bot import UtilityMasterBot

# Load environment variables
load_dotenv()


def main():
    TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")

    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    bot_instance = UtilityMasterBot(bot, dp)
    asyncio.run(bot_instance.run())


if __name__ == "__main__":
    main()
