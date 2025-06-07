from aiogram.dispatcher.middlewares.base import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import TelegramObject
from config.settings import Config
from services.api_client import GoogleSheetsClient


class DependencyMiddleware(BaseMiddleware):
    def __init__(self, config: Config, sheets: GoogleSheetsClient):
        super().__init__()
        self.config = config
        self.sheets = sheets

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["config"] = self.config
        data["sheets"] = self.sheets
        return await handler(event, data)
