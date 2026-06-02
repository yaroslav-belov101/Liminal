import asyncio
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.fsm.storage.memory import MemoryStorage

from handlers.start import router as start_router
from handlers.fetch import router as fetch_router

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота и увидеть меню"),
        BotCommand(command="help", description="Помощь по боту"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

async def main():
    dp.include_router(start_router)
    dp.include_router(fetch_router)

    await set_commands(bot)
    print("🌑 Liminal bot запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())