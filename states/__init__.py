from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    waiting_for_room = State()
    waiting_for_portions = State()
    waiting_for_payment = State()


class LanguageStates(StatesGroup):
    waiting_for_language = State()
