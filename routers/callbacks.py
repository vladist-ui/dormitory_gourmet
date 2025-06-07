from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from services.api_client import GoogleSheetsClient
from keyboards.inline import get_cancel_keyboard, get_order_confirmation_keyboard
from callbacks.reserve import ReserveCallback, CancelCallback
from config.settings import Config

router = Router()


class ReserveStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_room = State()
    waiting_for_receipt = State()


@router.callback_query(ReserveCallback.filter())
async def process_reserve(
    callback: CallbackQuery,
    callback_data: ReserveCallback,
    state: FSMContext,
    sheets: GoogleSheetsClient,
):
    print(f"Processing reserve callback for user {callback.from_user.id}")
    try:
        # Получаем данные анонса
        announcement = sheets.get_announcement_by_id(callback_data.announcement_id)
        if not announcement:
            await callback.answer("Анонс не найден", show_alert=True)
            return

        # Сохраняем данные в состояние
        await state.update_data(
            announcement_id=callback_data.announcement_id,
            dish_name=announcement["Название блюда"],
            price=announcement["Цена"],
        )

        # Отправляем сообщение с запросом количества порций
        await callback.message.edit_text(
            f"🍽 *{announcement['Название блюда']}*\n\n"
            f"💰 Цена за порцию: {announcement['Цена']}\n\n"
            f"Пожалуйста, введите количество порций:",
            reply_markup=get_cancel_keyboard(),
        )

        # Устанавливаем состояние ожидания количества порций
        await state.set_state(ReserveStates.waiting_for_amount)

    except Exception as e:
        print(f"Error in process_reserve: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@router.message(ReserveStates.waiting_for_amount)
async def process_amount(
    message: Message, state: FSMContext, sheets: GoogleSheetsClient
):
    try:
        try:
            portions = int(message.text)
            if portions <= 0:
                raise ValueError
        except ValueError:
            await message.answer(
                "Пожалуйста, введите корректное количество порций (целое положительное число):",
                reply_markup=get_cancel_keyboard(),
            )
            return

        data = await state.get_data()
        price = data["price"]
        total_amount = int(price) * portions
        await state.update_data(portions=portions)

        await message.answer(
            "Укажите ваш блок (например: 804a):",
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(ReserveStates.waiting_for_room)
    except Exception as e:
        print(f"Error in process_amount: {e}")
        await message.answer(
            "Произошла ошибка. Попробуйте начать бронирование заново.",
            reply_markup=get_cancel_keyboard(),
        )


@router.message(ReserveStates.waiting_for_room)
async def process_room(message: Message, state: FSMContext, sheets: GoogleSheetsClient):
    room = message.text.strip()
    await state.update_data(room=room)
    data = await state.get_data()
    portions = data["portions"]
    price = data["price"]
    total_amount = int(price) * int(portions)
    await message.answer(
        f"🍽 *{data['dish_name']}*\n"
        f"Блок: {room}\n"
        f"Количество порций: {portions}\n"
        f"💰 Общая сумма: {total_amount}\n\n"
        f"💳 Реквизиты для оплаты:\n"
        f"Тинькофф: +777777777777\n\n"
        f"Пожалуйста, переведите {total_amount} рублей и отправьте скриншот чека:",
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(ReserveStates.waiting_for_receipt)


@router.message(ReserveStates.waiting_for_receipt, F.photo)
async def process_receipt(
    message: Message, state: FSMContext, sheets: GoogleSheetsClient, config: Config
):
    try:
        data = await state.get_data()
        announcement_id = data.get("announcement_id")
        dish_name = data.get("dish_name")
        portions = data.get("portions")
        room = data.get("room")
        if not all([announcement_id, dish_name, portions, room]):
            await message.answer(
                "Ошибка: не все данные сохранены. Попробуйте начать бронирование заново.",
                reply_markup=get_cancel_keyboard(),
            )
            return
        photo = message.photo[-1]
        file_id = photo.file_id
        from datetime import datetime

        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = message.from_user.username or "-"
        order_id = str(message.message_id)
        sheets.add_order(
            user_id=message.from_user.id,
            username=username,
            room=room,
            portions=portions,
            dt=dt,
            dish_name=dish_name,
            order_id=order_id,
            canceled="Ожидает подтверждения",
        )
        for admin_id in config.tg_bot.admin_ids:
            try:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=f"🆕 Новый заказ!\n\n"
                    f"🍽 Блюдо: {dish_name}\n"
                    f"👤 Пользователь: {message.from_user.id} (@{username})\n"
                    f"🏢 Блок: {room}\n"
                    f"🍽 Количество порций: {portions}",
                    reply_markup=get_order_confirmation_keyboard(order_id),
                )
            except Exception as e:
                print(f"Error sending notification to admin {admin_id}: {e}")
        await message.answer(
            f"✅ Заказ успешно создан!\n\n"
            f"🍽 Блюдо: {dish_name}\n"
            f"🏢 Блок: {room}\n"
            f"🍽 Количество порций: {portions}\n\n"
            f"Спасибо за заказ! Мы проверим оплату и подтвердим ваш заказ."
        )
        await state.clear()
    except Exception as e:
        print(f"Error in process_receipt: {e}")
        await message.answer(
            "Произошла ошибка при обработке заказа. Пожалуйста, попробуйте позже."
        )


@router.callback_query(CancelCallback.filter())
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    try:
        # Сбрасываем состояние
        await state.clear()

        # Отправляем сообщение об отмене
        await callback.message.edit_text("❌ Бронирование отменено.", reply_markup=None)

    except Exception as e:
        print(f"Error in process_cancel: {e}")
        await callback.answer("Произошла ошибка при отмене", show_alert=True)
