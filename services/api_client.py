import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional


class GoogleSheetsClient:
    def __init__(self, creds_file: str):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        self.creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        self.client = gspread.authorize(self.creds)
        self.spreadsheet = self.client.open("Gourmet")

        # Проверка наличие листа Users и создаем его, если нет
        try:
            users = self.get_worksheet("Users")
            # Проверяем заголовки
            headers = users.row_values(1)
            if not headers or len(headers) < 2:
                print("Creating headers in Users worksheet")
                users.update("A1:B1", [["user_id", "language"]])
        except gspread.exceptions.WorksheetNotFound:
            print("Creating Users worksheet...")
            self.spreadsheet.add_worksheet(title="Users", rows=1000, cols=2)
            users = self.get_worksheet("Users")
            users.update("A1:B1", [["user_id", "language"]])
            print("Users worksheet created successfully")

    def get_worksheet(self, name: str):
        return self.spreadsheet.worksheet(name)

    def get_all_users(self) -> List[Dict[str, str]]:
        """Получить список всех пользователей"""
        try:
            users = self.get_worksheet("Users")
            #  все значения из таблицы
            all_values = users.get_all_values()
            print(f"All values from Users: {all_values}")

            # Преобразуем данные
            result = []
            for row in all_values:
                if (
                    not row or not row[0] or row[0] == "user_id"
                ):  # Пропускаем пустые строки и заголовок
                    continue

                user_id = str(row[0]).strip()
                language = str(row[1]).strip() if len(row) > 1 and row[1] else "ru"

                result.append({"user_id": user_id, "language": language})
                print(f"Added user: {user_id} with language {language}")

            print(f"Total users found: {len(result)}")
            return result

        except Exception as e:
            print(f"Error getting users: {e}")
            return []

    def get_unsent_announcements(self) -> List[Dict[str, Any]]:
        """Получить неотправленные анонсы"""
        anonce = self.get_worksheet("Anonces")
        all_values = anonce.get_all_records()
        headers = anonce.row_values(1)

        unsent = []
        for idx, row in enumerate(
            all_values, start=2
        ):  # start=2 потому что первая строка - заголовки
            if row.get("Отправлено", "").lower() == "false":
                announcement = dict(zip(headers, row.values()))
                announcement["row_index"] = idx  # Добавляем индекс строки
                unsent.append(announcement)
        return unsent

    def mark_announcement_sent(self, row_index: int):
        """Пометить анонс как отправленный"""
        try:
            anonce = self.get_worksheet("Anonces")
            # Находим столбец "Отправлено"
            headers = anonce.row_values(1)
            sent_column = (
                headers.index("Отправлено") + 1
            )  # +1 потому что индексация с 1
            print(f"Marking announcement in row {row_index} as sent")
            anonce.update_cell(row_index, sent_column, "TRUE")
            print("Successfully marked as sent")
        except Exception as e:
            print(f"Error marking announcement as sent: {e}")
            raise

    def add_user(self, user_id: int, language: str = "ru"):
        """Добавить нового пользователя"""
        try:
            print(f"Attempting to add user {user_id} with language {language}")
            users = self.get_worksheet("Users")
            print("Got worksheet 'Users'")

            # Проверяем, есть ли уже пользователь с таким user_id
            try:
                user_cell = users.find(str(user_id))
                if user_cell:
                    print(f"User {user_id} already exists, updating language")
                    users.update_cell(user_cell.row, 2, language)
                else:
                    print(f"Adding new user {user_id}")
                    users.append_row([str(user_id), language])
                    print("User added successfully")
            except Exception as e:
                print(f"Error in user operation: {e}")
                # Если не нашли пользователя, добавляем новую строку
                print("Adding new user row")
                users.append_row([str(user_id), language])
                print("User added successfully")
        except Exception as e:
            print(f"Critical error in add_user: {e}")
            raise

    def get_user_language(self, user_id: int) -> str:
        """Получить язык пользователя"""
        users = self.get_worksheet("Users")
        # Ищем строку, где первый столбец (индекс 0) равен user_id
        user_cell = users.find(str(user_id))
        if user_cell:
            return users.cell(user_cell.row, 2).value
        return "ru"

    def update_user_language(self, user_id: int, language: str):
        """Обновить язык пользователя"""
        users = self.get_worksheet("Users")
        user = users.find(str(user_id))
        if user:
            users.update_cell(user.row, 2, language)

    def add_order(
        self,
        user_id: int,
        username: str,
        room: str,
        portions: int,
        dt: str,
        dish_name: str,
        order_id: str,
        canceled: str = "Ожидает подтверждения",
    ):
        """Добавить новый заказ"""
        orders = self.get_worksheet("Orders")
        orders.append_row(
            [
                str(user_id),
                username,
                room,
                str(portions),
                dt,
                dish_name,
                order_id,
                canceled,
            ]
        )

    def update_order_status(self, order_id: str, status: str):
        """Обновить статус заказа"""
        orders = self.get_worksheet("Orders")
        # Преобразуем order_id в строку для поиска
        order_cell = orders.find(str(order_id))
        if order_cell:
            orders.update_cell(order_cell.row, 8, status)  # 8-й столбец - статус отмены
            return True
        return False

    def get_last_user_order(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить последний заказ пользователя"""
        orders = self.get_worksheet("Orders")
        # Получаем заголовки таблицы
        headers = orders.row_values(1)
        # Получаем все заказы
        all_orders = orders.get_all_records()
        # Фильтруем заказы пользователя
        user_orders = [order for order in all_orders if str(order['user_id']) == str(user_id)]
        if not user_orders:
            return None
        # Сортируем по дате (предполагая, что дата находится в 5-м столбце)
        sorted_orders = sorted(user_orders, key=lambda x: x[headers[4]], reverse=True)
        return sorted_orders[0]

    def get_announcement_by_id(self, row_index: int) -> Optional[Dict[str, Any]]:
        """Получить анонс по ID (номеру строки)"""
        try:
            anonce = self.get_worksheet("Anonces")
            headers = anonce.row_values(1)
            row_values = anonce.row_values(row_index)

            if not row_values:
                return None

            return dict(zip(headers, row_values))
        except Exception as e:
            print(f"Error getting announcement by id: {e}")
            return None
