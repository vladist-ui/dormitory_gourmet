import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config.settings import load_config
from routers import commands, callbacks
from middlewares import DependencyMiddleware
from services.api_client import GoogleSheetsClient


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

    config = load_config()
    bot = Bot(
        token=config.tg_bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Инициализация Google Sheets клиента
    sheets = GoogleSheetsClient(config.db.creds_file)

    # Регистрация роутеров
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)

    # Регистрация middleware
    dp.message.middleware(DependencyMiddleware(config, sheets))
    dp.callback_query.middleware(DependencyMiddleware(config, sheets))

    # Запуск бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
