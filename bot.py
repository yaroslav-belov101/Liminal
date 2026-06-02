import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.fsm.storage.memory import MemoryStorage
from services.database import init_db
from handlers.start import router as start_router
from handlers.fetch import router as fetch_router
from handlers.playlists import router as playlists_router
from handlers.flow import router as flow_router

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота и увидеть меню"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    dp.include_router(start_router)
    dp.include_router(fetch_router)
    dp.include_router(playlists_router)
    dp.include_router(flow_router)
    
    await set_commands(bot)
    print("🌑 Liminal bot запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())