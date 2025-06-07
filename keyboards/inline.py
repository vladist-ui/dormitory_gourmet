from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from callbacks.reserve import ReserveCallback, CancelCallback


def get_reserve_keyboard(announcement_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для бронирования"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Забронировать",
                    callback_data=ReserveCallback(
                        announcement_id=announcement_id
                    ).pack(),
                )
            ]
        ]
    )


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для отмены бронирования"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отменить", callback_data=CancelCallback().pack()
                )
            ]
        ]
    )


def get_language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru"),
        InlineKeyboardButton(text="English 🇬🇧", callback_data="lang_en"),
    )
    return builder.as_markup()


def get_order_confirmation_keyboard(order_id: str) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения заказа"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить", callback_data=f"confirm_{order_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить", callback_data=f"reject_{order_id}"
                ),
            ]
        ]
    )
