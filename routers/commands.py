from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config.settings import Config
from services.api_client import GoogleSheetsClient
from keyboards.inline import (
    get_reserve_keyboard,
    get_language_keyboard,
    get_order_confirmation_keyboard,
)
from states import OrderStates, LanguageStates
from filters.admin_filter import AdminFilter

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, sheets: GoogleSheetsClient):
    print(f"Processing /start command for user {message.from_user.id}")
    user_id = message.from_user.id


    users = sheets.get_all_users()
    user_exists = any(str(user["user_id"]) == str(user_id) for user in users)

    if not user_exists:
        print(f"Adding new user {user_id}")
        sheets.add_user(user_id)

    #Язык пользователя
    user_language = next(
        (user["language"] for user in users if str(user["user_id"]) == str(user_id)),
        "ru",
    )
    print(f"User language: {user_language}")

    # Приветсвие
    await message.answer(
        f"Привет! Я бот для управления анонсами блюд.\n"
        f"Текущий язык: {user_language}\n"
        f"Используйте /language для смены языка.",
        reply_markup=get_language_keyboard(),
    )


@router.message(Command("language"))
async def cmd_language(message: Message, state: FSMContext):
    await state.set_state(LanguageStates.waiting_for_language)
    await message.answer(
        "Выберите язык / Choose language:", reply_markup=get_language_keyboard()
    )


@router.callback_query(F.data.startswith("lang_"))
async def process_language_selection(
    callback: CallbackQuery, state: FSMContext, sheets: GoogleSheetsClient
):
    lang = callback.data.split("_")[1]
    user_id = callback.from_user.id
    sheets.update_user_language(user_id, lang)
    await state.clear()
    await callback.message.edit_text(
        "Язык успешно изменен!" if lang == "ru" else "Language successfully changed!"
    )


@router.message(Command("send_menu"))
async def cmd_send_menu(message: Message, sheets: GoogleSheetsClient, config: Config):
    print(f"Processing /send_menu command from user {message.from_user.id}")
    admin_filter = AdminFilter(config.tg_bot.admin_ids)
    if not await admin_filter(message):
        print(f"User {message.from_user.id} is not admin")
        await message.answer("Нет доступа.")
        return

    print("User is admin, getting unsent announcements")
    unsent = sheets.get_unsent_announcements()
    print(f"Found {len(unsent)} unsent announcements")

    if not unsent:
        await message.answer("Нет новых анонсов для отправки.")
        return

    users = sheets.get_all_users()
    print(f"Found {len(users)} users to send announcements to")

    if not users:
        await message.answer("Нет пользователей для рассылки.")
        return

    # сообщение админу
    try:
        await message.answer(
            f"🍽 *{unsent[0]['Название блюда']}*\n\n"
            f"{unsent[0]['Описание блюда']}\n\n"
            f"{unsent[0]['Текст сообщения']}\n\n"
            f"💰 Цена: {unsent[0]['Цена']}\n"
            f"⏰ Время: {unsent[0]['Время']}",
            reply_markup=get_reserve_keyboard(announcement_id=unsent[0]["row_index"]),
        )
        print(f"Successfully sent to admin {message.from_user.id}")
    except Exception as e:
        print(f"Error sending message to admin: {e}")

    # Отправка пользователям
    for announcement in unsent:
        print(f"Processing announcement: {announcement['Название блюда']}")
        for user in users:
            try:
                user_id = user["user_id"]
                if int(user_id) == message.from_user.id:
                    continue  # Пропускаем админа, так как уже отправили

                print(f"Sending to user {user_id}")
                await message.bot.send_message(
                    chat_id=int(user_id),
                    text=f"🍽 *{announcement['Название блюда']}*\n\n"
                    f"{announcement['Описание блюда']}\n\n"
                    f"💰 Цена: {announcement['Цена']}\n"
                    f"⏰ Время: {announcement['Время']}",
                    reply_markup=get_reserve_keyboard(
                        announcement_id=announcement["row_index"]
                    ),
                )
                print(f"Successfully sent to user {user_id}")
            except Exception as e:
                print(f"Error sending message to user {user_id}: {e}")

        print(f"Marking announcement as sent (row {announcement['row_index']})")
        sheets.mark_announcement_sent(announcement["row_index"])

    await message.answer("Рассылка завершена!")


@router.callback_query(F.data == "reserve")
async def process_reserve(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderStates.waiting_for_room)
    await callback.message.answer("Введите номер вашей комнаты:")


@router.message(OrderStates.waiting_for_room)
async def process_room(message: Message, state: FSMContext):
    await state.update_data(room=message.text)
    await state.set_state(OrderStates.waiting_for_portions)
    await message.answer("Введите количество порций:")


@router.message(OrderStates.waiting_for_portions)
async def process_portions(message: Message, state: FSMContext):
    try:
        portions = int(message.text)
        if portions <= 0:
            raise ValueError
        await state.update_data(portions=portions)
        await state.set_state(OrderStates.waiting_for_payment)
        await message.answer("Отправьте скриншот оплаты:")
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число порций.")


@router.message(OrderStates.waiting_for_payment, F.photo)
async def process_payment(
    message: Message, state: FSMContext, sheets: GoogleSheetsClient
):
    data = await state.get_data()
    photo = message.photo[-1]
    file_id = photo.file_id

    # Сохраняем заказ
    sheets.add_order(
        user_id=message.from_user.id,
        dish_name=data["dish_name"],
        room=data["room"],
        portions=data["portions"],
        payment_screenshot=file_id,
    )

    # Отправка уведомления админам
    for admin_id in Config.tg_bot.admin_ids:
        try:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=f"Новый заказ!\nКомната: {data['room']}\nПорций: {data['portions']}",
                reply_markup=get_order_confirmation_keyboard(str(message.message_id)),
            )
        except Exception as e:
            print(f"Error sending notification to admin {admin_id}: {e}")

    await state.clear()
    await message.answer("Спасибо за заказ! Ожидайте подтверждения от администратора.")


@router.callback_query(F.data.startswith(("confirm_", "reject_")))
async def process_order_confirmation(
    callback: CallbackQuery, sheets: GoogleSheetsClient, config: Config
):
    action, order_id = callback.data.split("_")
    orders_ws = sheets.get_worksheet("Orders")
    order_cell = orders_ws.find(order_id)
    if not order_cell:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    # Получаем данные заказа
    order_data = {
        "user_id": orders_ws.cell(order_cell.row, 1).value,
        "username": orders_ws.cell(order_cell.row, 2).value,
        "room": orders_ws.cell(order_cell.row, 3).value,
        "portions": orders_ws.cell(order_cell.row, 4).value,
        "dish_name": orders_ws.cell(order_cell.row, 6).value,
    }

    if action == "confirm":
        sheets.update_order_status(order_id, "Подтвержден")
        await callback.message.bot.send_message(
            chat_id=order_data["user_id"],
            text=f"✅ Ваш заказ подтвержден!\n\n"
            f"🍽 Блюдо: {order_data['dish_name']}\n"
            f"🏢 Блок: {order_data['room']}\n"
            f"🍽 Количество порций: {order_data['portions']}\n\n"
            f"Приятного аппетита! 🍽",
        )
    else:
        sheets.update_order_status(order_id, "Отменен")
        # Отправляем уведомление всем админам
        for admin_id in config.tg_bot.admin_ids:
            try:
                await callback.message.bot.send_message(
                    chat_id=admin_id,
                    text=f"❌ Заказ отменен!\n\n"
                    f"🍽 Блюдо: {order_data['dish_name']}\n"
                    f"👤 Пользователь: {order_data['user_id']} (@{order_data['username']})\n"
                    f"🏢 Блок: {order_data['room']}\n"
                    f"🍽 Количество порций: {order_data['portions']}",
                )
            except Exception as e:
                print(f"Error sending notification to admin {admin_id}: {e}")

        await callback.message.bot.send_message(
            chat_id=order_data["user_id"],
            text=f"❌ Ваш заказ был отменен администратором.\n\n"
            f"🍽 Блюдо: {order_data['dish_name']}\n"
            f"🏢 Блок: {order_data['room']}\n"
            f"🍽 Количество порций: {order_data['portions']}\n\n"
            f"Если у вас есть вопросы, пожалуйста, свяжитесь с администратором.",
        )

    await callback.message.edit_reply_markup(reply_markup=None)


@router.message(Command("nofood"))
async def cmd_nofood(message: Message, sheets: GoogleSheetsClient, config: Config):
    print(f"Processing /nofood command from user {message.from_user.id}")
    admin_filter = AdminFilter(config.tg_bot.admin_ids)
    if not await admin_filter(message):
        print(f"User {message.from_user.id} is not admin")
        await message.answer("Нет доступа.")
        return

    users = sheets.get_all_users()
    print(f"Found {len(users)} users to send notification to")

    if not users:
        await message.answer("Нет пользователей для рассылки.")
        return

    # Отправляем сообщение всем пользователям
    success_count = 0
    for user in users:
        try:
            user_id = user["user_id"]
            await message.bot.send_message(
                chat_id=int(user_id),
                text="⚠️ *Важное объявление*\n\n"
                "Сегодня еды не будет.\n"
                "Приносим извинения за неудобства.",
            )
            success_count += 1
        except Exception as e:
            print(f"Error sending notification to user {user_id}: {e}")

    await message.answer(
        f"✅ Уведомление отправлено {success_count} пользователям из {len(users)}"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, sheets: GoogleSheetsClient, config: Config):
    print(f"Processing /cancel command from user {message.from_user.id}")
    
    # последний заказ пользователя
    last_order = sheets.get_last_user_order(message.from_user.id)
    if not last_order:
        await message.answer("У вас нет активных заказов для отмены.")
        return

    # Получаем заголовки таблицы для правильного доступа к полям
    orders_ws = sheets.get_worksheet("Orders")
    headers = orders_ws.row_values(1)
    status_column = headers[7]  # 8-й столбец (индекс 7) - статус заказа
    order_id_column = headers[6]  # 7-й столбец (индекс 6) - ID заказа
    dish_name_column = headers[5]  # 6-й столбец (индекс 5) - название блюда
    room_column = headers[2]  # 3-й столбец (индекс 2) - блок
    portions_column = headers[3]  # 4-й столбец (индекс 3) - количество порций
    username_column = headers[1]  # 2-й столбец (индекс 1) - username

    # Проверяем, что заказ еще не отменен
    if last_order[status_column] != "Ожидает подтверждения":
        await message.answer("Этот заказ уже обработан и не может быть отменен.")
        return

    # Формируем статус отмены с датой
    from datetime import datetime
    cancel_status = f"Отменен пользователем {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Обновляем статус заказа
    sheets.update_order_status(last_order[order_id_column], cancel_status)

    # Отправляем уведомление админам
    for admin_id in config.tg_bot.admin_ids:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"❌ Заказ отменен пользователем!\n\n"
                     f"🍽 Блюдо: {last_order[dish_name_column]}\n"
                     f"👤 Пользователь: {last_order['user_id']} (@{last_order[username_column]})\n"
                     f"🏢 Блок: {last_order[room_column]}\n"
                     f"🍽 Количество порций: {last_order[portions_column]}\n"
                     f"⏰ Время отмены: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except Exception as e:
            print(f"Error sending notification to admin {admin_id}: {e}")

    # Отправляем подтверждение пользователю
    await message.answer(
        f"✅ Ваш последний заказ отменен:\n\n"
        f"🍽 Блюдо: {last_order[dish_name_column]}\n"
        f"🏢 Блок: {last_order[room_column]}\n"
        f"🍽 Количество порций: {last_order[portions_column]}\n\n"
        f"Администраторы уведомлены об отмене."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "🤖 *Dormitory Gourmet Bot*\n\n"
        "Этот бот помогает организовать заказы еды в общежитии.\n\n"
        "*Доступные команды:*\n"
        "• /start - Начать работу с ботом\n"
        "• /language - Изменить язык бота\n"
        "• /cancel - Отменить последний заказ\n"
        "• /help - Показать это сообщение\n\n"
        "*Как пользоваться ботом:*\n"
        "1. Дождитесь анонса блюда от администратора\n"
        "2. Нажмите кнопку 'Забронировать'\n"
        "3. Укажите количество порций\n"
        "4. Укажите ваш блок\n"
        "5. Оплатите заказ и отправьте скриншот чека\n"
        "6. Дождитесь подтверждения от администратора\n\n"
        "Если у вас возникли вопросы, обратитесь к администратору."
    )
    
    await message.answer(help_text, parse_mode="Markdown")
