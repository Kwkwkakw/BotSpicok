import re
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from config import BOT_TOKEN, ADMIN_IDS, STATUS_EMOJIS, STATUS_DESCRIPTIONS, STATUS_NAMES, ADMIN_USERNAMES, CHANNEL_IDS, LOG_CHANNEL_ID, SUGGESTION_CHANNEL_ID
from database import Database

# Состояния для обработки предложений
SUGGESTION_STATUS, SUGGESTION_DESIRED_STATUS, SUGGESTION_PROOF, SUGGESTION_REASON, SUGGESTION_USERNAME, SUGGESTION_DATA = range(6)
# Новые состояния для админ-функций
BROADCAST_MESSAGE, BLOCK_USER, UNBLOCK_USER = range(3, 6)

CHANNELS = {
    "hatakibalova": {
        "url": "https://t.me/licvidaciacollectionssss",
        "chat_id": CHANNEL_IDS["hatakibalova"],
        "title": "Хᴀᴛᴀ ᴋiʙᴀʟᴏʙᴀ"
    }
}

# Глобальный флаг техработ
MAINTENANCE_MODE = False

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    for channel in CHANNELS.values():
        try:
            member = await context.bot.get_chat_member(
                chat_id=channel["chat_id"], 
                user_id=user_id
            )
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            print(f"Ошибка проверки подписки: {e}")
            return False
    return True

async def send_subscription_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(channel["title"], url=channel["url"])]
        for channel in CHANNELS.values()
    ]
    keyboard.append([InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "👋 Наш бот является абсолютно бесплатным, поэтому пожалуйста,\n"
        "📢 Для использования бота необходимо подписаться на наши каналы:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

# Функция для логирования действий
async def log_action(action: str, user: dict, context: ContextTypes.DEFAULT_TYPE, details: str = ""):
    log_message = (
        f"🛠️ Действие: {action}\n"
        f"👤 Пользователь: {user.get('full_name', 'N/A')} (@{user.get('username', 'N/A')})\n"
        f"🆔 ID: {user.get('id', 'N/A')}\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    if details:
        log_message += f"📝 Детали: {details}\n"
    
    try:
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=log_message
        )
    except Exception as e:
        print(f"Ошибка при отправке лога: {e}")

# Состояния для админских действий
ADD_USER, REMOVE_USER = range(2)

db = Database()
USER_PAGE_CACHE: Dict[int, int] = {}
USER_LIST_CACHE = {}

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Проверка на блокировку
    if db.is_user_blocked(str(user.id)):
        await update.message.reply_text("🚫 Ваш аккаунт заблокирован. Обратитесь к администратору.")
        return
    
    # Проверка техработ
    global MAINTENANCE_MODE
    if MAINTENANCE_MODE:
        await update.message.reply_text("🔧 Бот временно недоступен из-за технических работ. Пожалуйста, попробуйте позже.")
        return
    
    if not await check_subscription(user.id, context):
        await send_subscription_request(update, context)
        return
    
    # Добавляем пользователя в базу бота
    db.add_bot_user(str(user.id))
    
    keyboard = [
        [InlineKeyboardButton("🔍 Проверить пользователя", callback_data='check_user')],
        [InlineKeyboardButton("📋 Список пользователей", callback_data='user_list_1')],
        [InlineKeyboardButton("👤 Мой профиль", callback_data='my_profile')],
        [InlineKeyboardButton("📨 Предложить пользователя", callback_data='suggest_user')]
    ]
    
    if update.effective_user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("🛠️ Админ панель", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (
        "👋 Добро пожаловать в бота 'Кодекс обмана'!\n"
        "Здесь вы можете проверить статус пользователя и узнать, можно ли ему доверять."
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)
    
    # Логирование запуска бота
    user_data = {
        'id': user.id,
        'username': user.username,
        'full_name': user.full_name
    }
    await log_action("Пользователь запустил бота", user_data, context)

# Обработчик предложения пользователя
async def suggest_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📨 Вы можете предложить себя или другого пользователя для внесения в список.\n\n"
        "Отправьте сообщение в следующем формате:\n\n"
        "1. Желаемый статус: \n"
        "2. Доказательство (фото или ссылка): \n"
        "3. Причина/Обоснование: \n"
        "4. Юзернейм (если предлагаете другого пользователя): @username\n\n"
        "Пример:\n"
        "1. Желаемый статус: медийка\n"
        "2. Доказательство (фото или ссылка): https://example.com/proof.jpg\n"
        "3. Причина/Обоснование: Это известный пользователь\n"
        "4. Юзернейм (если предлагаете другого пользователя): @username"
    )
    return SUGGESTION_DATA

# Обработка данных предложения
async def handle_suggestion_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    pattern = re.compile(
        r"1\.\s*Желаемый статус:\s*(.+?)\s*"
        r"2\.\s*Доказательство \(фото или ссылка\):\s*(.+?)\s*"
        r"3\.\s*Причина\/Обоснование:\s*([\s\S]+?)\s*"
        r"4\.\s*Юзернейм \(если предлагаете другого пользователя\):\s*@?(\w+)",
        re.IGNORECASE
    )
    
    match = pattern.search(text)
    if not match:
        await update.message.reply_text(
            "❌ Неверный формат. Пожалуйста, отправьте данные в следующем формате:\n\n"
            "1. Желаемый статус: \n"
            "2. Доказательство (фото или ссылка): \n"
            "3. Причина/Обоснование: \n"
            "4. Юзернейм (если предлагаете другого пользователя): @username\n\n"
            "Пример:\n"
            "1. Желаемый статус: media\n"
            "2. Доказательство (фото или ссылка): https://example.com/proof.jpg\n"
            "3. Причина/Обоснование: Это известный пользователь\n"
            "4. Юзернейм (если предлагаете другого пользователя): @username"
        )
        return SUGGESTION_DATA
    
    desired_status, proof, reason, username = match.groups()
    desired_status = desired_status.strip().lower()
    username = username.strip().lower()
    
    # Нормализация статусов
    status_mapping = {
        'медийка': 'media',
        'фейм': 'fame',
        'верифи': 'verify',
        'верификация': 'verify',
        'гарант': 'garant',
        'скам': 'scam',
        'бомж': 'beach',
        'нью': 'new',
        'педофил': 'pdf'
    }
    
    desired_status = status_mapping.get(desired_status, desired_status)
    
    # Проверка валидности статуса
    valid_statuses = ['verify', 'garant', 'media', 'fame', 'scam', 'beach', 'new', 'pdf']
    if desired_status not in valid_statuses:
        await update.message.reply_text(
            f"❌ Неверный статус. Доступные варианты: {', '.join(valid_statuses)}.\n"
            "Пожалуйста, укажите корректный статус:"
        )
        return SUGGESTION_DATA
    
    suggested_by = update.effective_user.username or str(update.effective_user.id)
    
    # Сохранение предложки в базу
    db.add_suggestion(
        username=username,
        desired_status=desired_status,
        proof=proof,
        reason=reason,
        suggested_by=suggested_by
    )
    
    # Отправка предложки в канал
    suggestion_message = (
        f"📨 Новая предложка пользователя:\n\n"
        f"👤 Пользователь: @{username}\n"
        f"⭐ Желаемый статус: {STATUS_NAMES.get(desired_status, desired_status)}\n"
        f"📝 Причина: {reason}\n"
        f"📎 Доказательство: {proof}\n"
        f"🤵 Предложил: @{suggested_by}\n\n"
        f"🆔 ID: {update.effective_user.id}"
    )
    
    try:
        await context.bot.send_message(
            chat_id=SUGGESTION_CHANNEL_ID,
            text=suggestion_message
        )
        
        print(f"Предложка успешно отправлена в канал {SUGGESTION_CHANNEL_ID}")
        print(f"Содержимое сообщения: {suggestion_message}")
        
        await update.message.reply_text(
            "✅ Ваша предложка успешно отправлена на рассмотрение администраторам.\n"
            "Спасибо за участие!"
        )
        
        # Логирование действия
        user_data = {
            'id': update.effective_user.id,
            'username': update.effective_user.username,
            'full_name': update.effective_user.full_name
        }
        details = f"Предложил @{username} на статус {desired_status}"
        await log_action("Пользователь отправил предложку", user_data, context, details)
        
    except Exception as e:
        print(f"Ошибка при отправке предложки: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке предложки. Попробуйте позже."
        )
    
    return ConversationHandler.END

# Показать список пользователей
async def show_user_list(update: Update, page: int = 1):
    query = update.callback_query
    await query.answer()
    
    # Используем кэш если есть
    if not USER_LIST_CACHE:
        USER_LIST_CACHE['users'] = db.get_all_users()
        USER_LIST_CACHE['timestamp'] = datetime.now()
    
    # Если кэш устарел (старше 5 минут)
    elif (datetime.now() - USER_LIST_CACHE['timestamp']).total_seconds() > 300:
        USER_LIST_CACHE['users'] = db.get_all_users()
        USER_LIST_CACHE['timestamp'] = datetime.now()
    
    users = USER_LIST_CACHE['users']
    
    if not users:
        await query.edit_message_text("Список пользователей пуст.")
        return
    
    total_pages = (len(users) // 20 + (1 if len(users) % 20 else 0))
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * 20
    end_idx = start_idx + 20
    page_users = users[start_idx:end_idx]
    
    message = f"📋 Список пользователей (Страница {page}/{total_pages}):\n\n"
    prev_status = None
    
    for username, status in page_users:
        if status != prev_status:
            if prev_status is not None:
                message += "——————————————————\n"
            prev_status = status
        
        emoji = STATUS_EMOJIS.get(status, '')
        status_name = STATUS_NAMES.get(status, status.capitalize())
        message += f"{emoji} {status_name} - @{username}\n"
    
    keyboard = []
    if page > 1:
        keyboard.append(InlineKeyboardButton("⬅️ Назад", callback_data=f'user_list_{page-1}'))
    if page < total_pages:
        keyboard.append(InlineKeyboardButton("➡️ Вперед", callback_data=f'user_list_{page+1}'))
    
    keyboard = [keyboard] if keyboard else []
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)

# Показать профиль пользователя
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    
    # Получение статуса пользователя
    if user.id in ADMIN_IDS:
        status = 'admin'
    else:
        status = db.get_user_status(user.username or str(user.id))
    
    # Определение эмодзи и названия статуса
    if status:
        emoji = STATUS_EMOJIS.get(status, '')
        status_name = STATUS_NAMES.get(status, status.capitalize())
    else:
        emoji = '❓'
        status_name = "Отсутствует"
    
    description = STATUS_DESCRIPTIONS.get(status, 'Статус не установлен') if status else "Статус не установлен"
    
    message = (
        f"👤 Ваш профиль:\n\n"
        f"🪪 Имя: {user.full_name}\n"
        f"{emoji} Статус: {status_name}\n"
        f"🆔 ID: {user.id}\n"
        f"📃 Username: @{user.username if user.username else 'Отсутствует'}\n"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup)

# Функция для генерации и отправки статистики
async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        total_bot_users = db.get_total_bot_users()
        total_listed_users = db.get_total_listed_users()
        total_admins = len(ADMIN_IDS)
        status_counts = db.get_status_counts()
    except Exception as e:
        print(f"Ошибка получения статистики: {e}")
        await query.edit_message_text("❌ Ошибка получения статистики")
        return

    # Генерация HTML
    status_table = ""
    for status, count in status_counts.items():
        status_name = STATUS_NAMES.get(status, status.capitalize())
        emoji = STATUS_EMOJIS.get(status, '')
        status_table += f"""
        <tr>
            <td>{emoji} {status_name}</td>
            <td>{count}</td>
        </tr>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Статистика бота</title>
        <style>
            body {{
                background-color: #0a0a0a;
                background-image: url('https://i.pinimg.com/originals/1b/3b/8f/1b3b8f7a8e2a1e4e7b0e7d0a3b3e3e3e.jpg');
                background-size: cover;
                color: #00ff00;
                font-family: 'Courier New', monospace;
                padding: 20px;
            }}
            .container {{
                background-color: rgba(0, 0, 0, 0.85);
                border: 1px solid #00ff00;
                border-radius: 10px;
                padding: 30px;
                margin: 20px auto;
                width: 80%;
                max-width: 600px;
                box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
            }}
            h1 {{
                text-align: center;
                color: #00ff00;
                text-shadow: 0 0 10px #00ff00;
                margin-bottom: 30px;
                font-size: 28px;
                border-bottom: 2px solid #00ff00;
                padding-bottom: 10px;
            }}
            .stat-item {{
                margin: 20px 0;
                padding: 15px;
                background-color: rgba(0, 30, 0, 0.4);
                border-left: 4px solid #00ff00;
                border-radius: 5px;
                transition: all 0.3s;
            }}
            .stat-item:hover {{
                background-color: rgba(0, 50, 0, 0.6);
                transform: translateX(10px);
            }}
            .stat-label {{
                font-size: 18px;
                margin-bottom: 8px;
                color: #00cc00;
            }}
            .stat-value {{
                font-size: 32px;
                font-weight: bold;
                color: #ffffff;
                text-shadow: 0 0 8px #00ff00;
            }}
            .status-table {{
                width: 100%;
                margin-top: 20px;
                border-collapse: collapse;
            }}
            .status-table th, .status-table td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #00ff00;
            }}
            .status-table th {{
                background-color: rgba(0, 50, 0, 0.5);
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                font-size: 14px;
                color: #008800;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 СТАТИСТИКА БОТА</h1>
            
            <div class="stat-item">
                <div class="stat-label">👤 Всего пользователей бота</div>
                <div class="stat-value">{total_bot_users}</div>
            </div>
            
            <div class="stat-item">
                <div class="stat-label">📝 Пользователей в базе</div>
                <div class="stat-value">{total_listed_users}</div>
            </div>
            
            <div class="stat-item">
                <div class="stat-label">👑 Администраторов</div>
                <div class="stat-value">{total_admins}</div>
            </div>
            
            <table class="status-table">
                <thead>
                    <tr>
                        <th>Статус</th>
                        <th>Количество</th>
                    </tr>
                </thead>
                <tbody>
                    {status_table}
                </tbody>
            </table>
            
            <div class="footer">
                {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
    </body>
    </html>
    """
    
    # Сохранение в файл
    filename = "statistics.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # Отправка файла
    try:
        await context.bot.send_document(
            chat_id=update.effective_user.id,
            document=open(filename, "rb"),
            caption="📊 Статистика бота"
        )
        os.remove(filename)  # Удаление временного файла
    except Exception as e:
        print(f"Ошибка отправки статистики: {e}")
        await query.edit_message_text("❌ Ошибка отправки статистики")

# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Проверка подписки
    if query.data == 'check_subscription':
        if await check_subscription(query.from_user.id, context):
            await start(update, context)
        else:
            await query.answer("Вы не подписаны на все каналы!", show_alert=True)
        return
    
    # Проверка подписки для других действий
    if not await check_subscription(query.from_user.id, context):
        await send_subscription_request(update, context)
        return
    
    # Обработка кнопки предложки
    if query.data == 'suggest_user':
        await suggest_user(update, context)
        return SUGGESTION_DATA
    
    # Обработка админских кнопок
    if query.data == 'statistics':
        if update.effective_user.id not in ADMIN_IDS:
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        await show_statistics(update, context)
        return
    
    if query.data == 'maintenance':
        if update.effective_user.id not in ADMIN_IDS:
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        # Рассылка уведомления
        users = db.get_all_bot_users()
        for user_id in users:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🔧 Внимание! Бот временно недоступен из-за технических работ. Приносим извинения за неудобства."
                )
                await asyncio.sleep(0.05)  # Задержка между сообщениями
            except Exception as e:
                print(f"Ошибка рассылки техработ: {e}")
        
        await query.edit_message_text(
            "✅ Уведомление о технических работах разослано всем пользователям."
        )
        
        # Логирование
        admin_data = {
            'id': update.effective_user.id,
            'username': update.effective_user.username,
            'full_name': update.effective_user.full_name
        }
        await log_action("Рассылка о техработах", admin_data, context)
        return
    
    if query.data == 'broadcast':
        if update.effective_user.id not in ADMIN_IDS:
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        await query.edit_message_text("📢 Введите сообщение для рассылки всем пользователям:")
        return BROADCAST_MESSAGE
    
    if query.data == 'block_user':
        if update.effective_user.id not in ADMIN_IDS:
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        await query.edit_message_text(
            "⛔ Введите username пользователя для блокировки:\n"
            "Пример: @username"
        )
        return BLOCK_USER
    
    if query.data == 'unblock_user':
        if update.effective_user.id not in ADMIN_IDS:
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        await query.edit_message_text(
            "✅ Введите username пользователя для разблокировки:\n"
            "Пример: @username"
        )
        return UNBLOCK_USER
    
    if query.data == 'add_user':
        if update.effective_user.id not in ADMIN_IDS:
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        await query.edit_message_text(
            "➕ Введите username и статус пользователя:\n"
            "Пример: @username status\n\n"
            "Доступные статусы: verify, garant, media, fame, scam, beach, new, pdf"
        )
        return ADD_USER
    
    if query.data == 'remove_user':
        if update.effective_user.id not in ADMIN_IDS:
            await query.answer("❌ У вас нет прав для выполнения этой команды.", show_alert=True)
            return
        
        await query.edit_message_text(
            "➖ Введите username пользователя для удаления:\n"
            "Пример: @username"
        )
        return REMOVE_USER
    
    # Обработка других кнопок
    if query.data == 'check_user':
        await query.edit_message_text(
            "Введите username пользователя для проверки (например, @username или просто username):"
        )
        return
    
    if query.data.startswith('user_list_'):
        page = int(query.data.split('_')[-1])
        await show_user_list(update, page)
        return
    
    if query.data == 'my_profile':
        await show_profile(update, context)
        return
    
    if query.data == 'admin_panel':
        if update.effective_user.id not in ADMIN_IDS:
            await query.edit_message_text("❌ У вас нет доступа к админ-панели.")
            return
        
        keyboard = [
            [InlineKeyboardButton("➕ Добавить пользователя", callback_data='add_user'),
             InlineKeyboardButton("➖ Удалить пользователя", callback_data='remove_user')],
            [InlineKeyboardButton("📢 Рассылка", callback_data='broadcast'),
             InlineKeyboardButton("📊 Статистика", callback_data='statistics')],
            [InlineKeyboardButton("🔧 Тех работы", callback_data='maintenance'),
             InlineKeyboardButton("⛔ Заблокировать", callback_data='block_user')],
            [InlineKeyboardButton("✅ Разблокировать", callback_data='unblock_user')],
            [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🛠️ Админ панель:", reply_markup=reply_markup)
        return
    
    if query.data == 'back_to_main':
        keyboard = [
            [InlineKeyboardButton("🔍 Проверить пользователя", callback_data='check_user')],
            [InlineKeyboardButton("📋 Список пользователей", callback_data='user_list_1')],
            [InlineKeyboardButton("👤 Мой профиль", callback_data='my_profile')],
            [InlineKeyboardButton("📨 Предложить пользователя", callback_data='suggest_user')]
        ]
        if update.effective_user.id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("🛠️ Админ панель", callback_data='admin_panel')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Главное меню:", reply_markup=reply_markup)
        return

# Проверка пользователя
async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if re.match(r'^\s*1\.\s*Желаемый статус:', text, re.IGNORECASE):
        return
    
    username = re.sub(r'^@', '', text).lower()
    
    # Проверка на администратора
    if username in ADMIN_USERNAMES.values():
        for admin_id, admin_username in ADMIN_USERNAMES.items():
            if admin_username.lower() == username.lower():
                status = 'admin'
                username = admin_username
                break
    else:
        status = db.get_user_status(username)
    
    if not status:
        await update.message.reply_text(
            f"🔍 Пользователь @{username} не найден в нашей базе данных.\n\n"
            "Вы можете предложить их внесение нашим Администраторам:\n"
            "@dev_sv4, @godkivalovskiy"
        )
        return
    
    emoji = STATUS_EMOJIS.get(status, '')
    status_name = STATUS_NAMES.get(status, status.capitalize())
    description = STATUS_DESCRIPTIONS.get(status, 'Неизвестный статус')
    
    await update.message.reply_text(
        f"🔍 Результат проверки: @{username}\n\n"
        f"{emoji} Статус: {status_name}\n"
        f"📝 Описание: {description}"
    )

# Добавление пользователя
async def handle_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    text = update.message.text.strip()
    match = re.match(r'^/add\s+@?(\w+)\s+(verify|garant|scam|beach|new|pdf|media|fame)$', text, re.IGNORECASE)
    
    if not match:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте:\n"
            "/add @username status\n\n"
            "Доступные статусы: verify, garant, scam, beach, new, pdf, media, fame\n\n"
            "Пример: /add @username scam"
        )
        return
    
    username, status = match.groups()
    db.add_user(username, status.lower())
    
    # Сброс кэша списка пользователей
    if USER_LIST_CACHE:
        USER_LIST_CACHE.clear()
    
    status_name = STATUS_NAMES.get(status, status.capitalize())
    await update.message.reply_text(f"✅ Пользователь @{username} успешно добавлен с статусом: {status_name}")

# Удаление пользователя
async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    text = update.message.text.strip()
    match = re.match(r'^/remove\s+@?(\w+)$', text, re.IGNORECASE)
    
    if not match:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте:\n"
            "/remove @username\n\n"
            "Пример: /remove @username"
        )
        return
    
    username = match.group(1)
    
    if db.get_user_status(username):
        db.remove_user(username)
        
        # Сброс кэша списка пользователей
        if USER_LIST_CACHE:
            USER_LIST_CACHE.clear()
            
        await update.message.reply_text(f"✅ Пользователь @{username} успешно удален из базы данных.")
    else:
        await update.message.reply_text(f"❌ Пользователь @{username} не найден в базе данных.")

# Рассылка сообщений
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return ConversationHandler.END
    
    message_text = update.message.text
    users = db.get_all_bot_users()
    total_users = len(users)
    
    if total_users == 0:
        await update.message.reply_text("❌ Нет пользователей для рассылки.")
        return ConversationHandler.END
    
    # Статусное сообщение
    status_msg = await update.message.reply_text(f"📢 Начата рассылка на {total_users} пользователей...\n"
                                                f"🔄 Отправлено: 0/{total_users} (0%)")
    
    success = 0
    fail = 0
    
    for i, user_id in enumerate(users):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message_text
            )
            success += 1
        except Exception as e:
            print(f"Ошибка рассылки: {e}")
            fail += 1
        
        # Обновление статуса каждые 10 сообщений или последнее сообщение
        if i % 10 == 0 or i == total_users - 1:
            percent = int((i + 1) / total_users * 100)
            progress = "🟢" * (percent // 10) + "⚪" * (10 - percent // 10)
            try:
                await status_msg.edit_text(
                    f"📢 Рассылка на {total_users} пользователей...\n"
                    f"🔄 Отправлено: {i+1}/{total_users} ({percent}%)\n"
                    f"{progress}\n"
                    f"✅ Успешно: {success} | ❌ Ошибок: {fail}"
                )
            except:
                pass
        
        # Задержка между сообщениями
        await asyncio.sleep(0.05)  # 50 мс
    
    # Итоговое сообщение
    await status_msg.edit_text(
        f"📢 Рассылка завершена:\n"
        f"👤 Всего пользователей: {total_users}\n"
        f"✅ Успешно: {success}\n"
        f"❌ Неудачно: {fail}"
    )
    
    # Логирование
    admin_data = {
        'id': update.effective_user.id,
        'username': update.effective_user.username,
        'full_name': update.effective_user.full_name
    }
    await log_action("Рассылка сообщения", admin_data, context, f"Текст: {message_text[:50]}...")
    return ConversationHandler.END

# Блокировка пользователя
async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return ConversationHandler.END
    
    text = update.message.text.strip()
    username = re.sub(r'^@', '', text).lower()
    
    if not username:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте:\n"
            "/block @username\n\n"
            "Пример: /block @username"
        )
        return ConversationHandler.END
    
    if db.block_user(username):
        await update.message.reply_text(f"⛔ Пользователь @{username} успешно заблокирован.")
    else:
        await update.message.reply_text(f"❌ Пользователь @{username} не найден или уже заблокирован.")
    
    # Логирование
    admin_data = {
        'id': update.effective_user.id,
        'username': update.effective_user.username,
        'full_name': update.effective_user.full_name
    }
    await log_action("Блокировка пользователя", admin_data, context, f"Пользователь: @{username}")
    return ConversationHandler.END

# Разблокировка пользователя
async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return ConversationHandler.END
    
    text = update.message.text.strip()
    username = re.sub(r'^@', '', text).lower()
    
    if not username:
        await update.message.reply_text(
            "❌ Неверный формат. Используйте:\n"
            "/unblock @username\n\n"
            "Пример: /unblock @username"
        )
        return ConversationHandler.END
    
    if db.unblock_user(username):
        await update.message.reply_text(f"✅ Пользователь @{username} успешно разблокирован.")
    else:
        await update.message.reply_text(f"❌ Пользователь @{username} не найден или не был заблокирован.")
    
    # Логирование
    admin_data = {
        'id': update.effective_user.id,
        'username': update.effective_user.username,
        'full_name': update.effective_user.full_name
    }
    await log_action("Разблокировка пользователя", admin_data, context, f"Пользователь: @{username}")
    return ConversationHandler.END

# Отмена действия
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END

# Админ панель
async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.answer("❌ У вас нет доступа к админ-панели.", show_alert=True)
        else:
            await update.message.reply_text("❌ У вас нет доступа к админ-панели.")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить пользователя", callback_data='add_user'),
         InlineKeyboardButton("➖ Удалить пользователя", callback_data='remove_user')],
        [InlineKeyboardButton("📢 Рассылка", callback_data='broadcast'),
         InlineKeyboardButton("📊 Статистика", callback_data='statistics')],
        [InlineKeyboardButton("🔧 Тех работы", callback_data='maintenance'),
         InlineKeyboardButton("⛔ Заблокировать", callback_data='block_user')],
        [InlineKeyboardButton("✅ Разблокировать", callback_data='unblock_user')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text("🛠️ Админ панель:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("🛠️ Админ панель:", reply_markup=reply_markup)
    
    return

# Главная функция
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('panel', panel_command))
    application.add_handler(CommandHandler('add', handle_add_command))
    application.add_handler(CommandHandler('remove', remove_user))
    application.add_handler(CommandHandler('block', block_user))
    application.add_handler(CommandHandler('unblock', unblock_user))
    application.add_handler(CommandHandler('broadcast', handle_broadcast))
    
    # Обработчик предложений
    suggestion_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(suggest_user, pattern='^suggest_user$')],
        states={
            SUGGESTION_DATA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_suggestion_data)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=True
    )
    
    # Обработчик админских действий
    admin_conv_handler = ConversationHandler(
        entry_points=[],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast)],
            BLOCK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, block_user)],
            UNBLOCK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, unblock_user)],
            ADD_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_command)],
            REMOVE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_user)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Регистрируем обработчики с приоритетом
    application.add_handler(suggestion_conv_handler)
    application.add_handler(admin_conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Обработчик проверки пользователя (низкий приоритет)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^\s*1\.\s*Желаемый статус:'), 
        check_user
    ))
    
    application.run_polling()

if __name__ == '__main__':
    main()