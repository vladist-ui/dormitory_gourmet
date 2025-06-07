from aiogram.filters.callback_data import CallbackData


class ReserveCallback(CallbackData, prefix="reserve"):
    announcement_id: int


class CancelCallback(CallbackData, prefix="cancel"):
    pass

