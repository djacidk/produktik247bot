from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, filters, MessageHandler
from telegram.error import TimedOut
import json
import logging
import sys
import io
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные из файла .env в систему
load_dotenv()

# Достаем значения
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    exit("Ошибка: TOKEN не найден в переменной окружения!")
    
# Исправляем кодировку для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Отключаем избыточное логирование
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Updater").setLevel(logging.WARNING)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    force=True
)

# Список возможных статусов
ORDER_STATUSES = ["Собирается", "Готовится", "Отправлен", "Доставлен"]

# Загружаем товары из JSON файла
def load_products():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Файл products.json не найден!")
        return {}

# Загружаем заказы из JSON файла
def load_orders():
    try:
        with open('orders.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Файл orders.json не найден!")
        return []

# Сохраняем заказы в файл
def save_orders(orders):
    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

# Создаем новый заказ
def create_order(order_data):
    orders = load_orders()
    
    # Генерируем уникальный номер заказа
    order_number = len(orders) + 1
    
    new_order = {
        "order_number": order_number,
        "user_id": order_data["user_id"],
        "username": order_data["username"],
        "item_id": order_data["item_id"],
        "item_name": order_data["item_name"],
        "category": order_data["category"],
        "quantity": order_data["quantity"],
        "price_per_unit": order_data["price_per_unit"],
        "total_price": order_data["total_price"],
        "timestamp": order_data["timestamp"],
        "status": "Собирается"  # Начальный статус
    }
    
    orders.append(new_order)
    save_orders(orders)
    
    return new_order

async def set_commands(application):
    """Устанавливает команды бота"""
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("catalog", "Открыть каталог товаров"),
        BotCommand("orders", "Просмотреть мои заказы"),
        BotCommand("help", "Помощь")
    ]
    await application.bot.set_my_commands(commands)
    print("✅ Команды бота установлены")
    sys.stdout.flush()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаем постоянную кнопку "Каталог" 
    keyboard = [['Каталог']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = """
🤖 Добро пожаловать в магазин продуктов!

🛒 Доступные команды:
/catalog - Открыть каталог товаров
/orders - Просмотреть ваши заказы
/help - Помощь

Нажмите кнопку 'Каталог' для начала покупок!
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Показываем категории товаров
    await show_categories(update, context)

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список заказов пользователя"""
    user_id = update.effective_user.id
    orders = load_orders()
    
    user_orders = [order for order in orders if order["user_id"] == user_id]
    
    if not user_orders:
        await update.message.reply_text("У вас пока нет заказов.")
        return
    
    orders_text = "📋 Ваши заказы:\n\n"
    for order in reversed(user_orders[-5:]):  # Показываем последние 5 заказов
        orders_text += f"№{order['order_number']} - {order['item_name']} ({order['quantity']} шт.)\n"
        orders_text += f"Статус: {order['status']}\n"
        orders_text += f"Стоимость: ${order['total_price']}\n"
        orders_text += "➖➖➖\n"
    
    await update.message.reply_text(orders_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 Доступные команды:
/start - Запустить бота
/catalog - Открыть каталог товаров
/orders - Просмотреть ваши заказы
/help - Показать помощь

🛒 Чтобы сделать заказ:
1. Нажмите кнопку 'Каталог' или команду /catalog
2. Выберите категорию
3. Выберите товар
4. Укажите количество
    """
    await update.message.reply_text(help_text)

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Загружаем товары
    products = load_products()
    
    # Создаем inline-кнопки категорий
    keyboard = []
    for category_key, category_data in products.items():
        button = InlineKeyboardButton(
            category_data['name'], 
            callback_data=f"cat_{category_key}"
        )
        keyboard.append([button])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Редактируем текущее сообщение
    message_text = "📂 Выберите категорию:"
    
    if update.message:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.message.edit_text(
            message_text,
            reply_markup=reply_markup
        )
        # Подтверждаем callback (убирает "кружок" ожидания)
        await update.callback_query.answer()
    
    sys.stdout.flush()

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE, category_key: str):
    """Показывает товары выбранной категории"""
    products = load_products()
    
    # Проверяем, существует ли категория
    if category_key not in products:
        if update.callback_query:
            await update.callback_query.answer("Категория не найдена")
        return
    
    category_data = products[category_key]
    items = category_data.get('items', {})
    
    # Создаем inline-кнопки товаров
    keyboard = []
    for item_id, item_data in items.items():
        button_text = f"{item_data['name']} - ${item_data['price']}"
        button = InlineKeyboardButton(
            button_text,
            callback_data=f"item_{item_id}"
        )
        keyboard.append([button])
    
    # Добавляем кнопку "Назад" к категориям
    back_button = InlineKeyboardButton("🔙 Назад к категориям", callback_data="back_to_categories")
    keyboard.append([back_button])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Редактируем текущее сообщение с товарами
    message_text = f"🛒 Товары в категории '{category_data['name']}':"
    
    if update.callback_query:
        await update.callback_query.message.edit_text(
            message_text,
            reply_markup=reply_markup
        )
        # Подтверждаем callback
        await update.callback_query.answer()
    
    sys.stdout.flush()

async def show_quantity_keyboard(query, item_id):
    """Показывает цифровую клавиатуру для ввода количества"""
    # Создаем цифровую клавиатуру 3x3 с дополнительными кнопками
    keyboard = [
        [InlineKeyboardButton("1", callback_data=f"qty_1_{item_id}"),
         InlineKeyboardButton("2", callback_data=f"qty_2_{item_id}"),
         InlineKeyboardButton("3", callback_data=f"qty_3_{item_id}")],
        [InlineKeyboardButton("4", callback_data=f"qty_4_{item_id}"),
         InlineKeyboardButton("5", callback_data=f"qty_5_{item_id}"),
         InlineKeyboardButton("6", callback_data=f"qty_6_{item_id}")],
        [InlineKeyboardButton("7", callback_data=f"qty_7_{item_id}"),
         InlineKeyboardButton("8", callback_data=f"qty_8_{item_id}"),
         InlineKeyboardButton("9", callback_data=f"qty_9_{item_id}")],
        [InlineKeyboardButton("⌫", callback_data=f"qty_backspace_{item_id}"),  # Удалить символ
         InlineKeyboardButton("0", callback_data=f"qty_0_{item_id}"),
         InlineKeyboardButton("❌", callback_data=f"qty_clear_{item_id}")],    # Стереть всё
        [InlineKeyboardButton("✅ Ввод", callback_data=f"qty_enter_{item_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "🔢 Введите количество товара:\n\nТекущее количество: 0"
    
    await query.message.edit_text(message_text, reply_markup=reply_markup)
    await query.answer()

async def update_quantity_display(query, current_quantity, item_id):
    """Обновляет отображение текущего количества на клавиатуре"""
    # Создаем цифровую клавиатуру 3x3 с дополнительными кнопками
    keyboard = [
        [InlineKeyboardButton("1", callback_data=f"qty_1_{item_id}"),
         InlineKeyboardButton("2", callback_data=f"qty_2_{item_id}"),
         InlineKeyboardButton("3", callback_data=f"qty_3_{item_id}")],
        [InlineKeyboardButton("4", callback_data=f"qty_4_{item_id}"),
         InlineKeyboardButton("5", callback_data=f"qty_5_{item_id}"),
         InlineKeyboardButton("6", callback_data=f"qty_6_{item_id}")],
        [InlineKeyboardButton("7", callback_data=f"qty_7_{item_id}"),
         InlineKeyboardButton("8", callback_data=f"qty_8_{item_id}"),
         InlineKeyboardButton("9", callback_data=f"qty_9_{item_id}")],
        [InlineKeyboardButton("⌫", callback_data=f"qty_backspace_{item_id}"),  # Удалить символ
         InlineKeyboardButton("0", callback_data=f"qty_0_{item_id}"),
         InlineKeyboardButton("❌", callback_data=f"qty_clear_{item_id}")],    # Стереть всё
        [InlineKeyboardButton("✅ Ввод", callback_data=f"qty_enter_{item_id}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    display_quantity = current_quantity if current_quantity else "0"
    message_text = f"🔢 Введите количество товара:\n\nТекущее количество: {display_quantity}"
    
    await query.message.edit_text(message_text, reply_markup=reply_markup)
    await query.answer()

async def update_status_message(query, order_number):
    """Обновление сообщения со статусом заказа"""
    try:
        orders = load_orders()
        
        # Находим заказ по номеру
        order = None
        order_index = None
        for i, o in enumerate(orders):
            if str(o["order_number"]) == order_number:
                order = o
                order_index = i
                break
        
        if order and order_index is not None:
            # Обновляем статус (по кругу)
            current_status_index = ORDER_STATUSES.index(order["status"])
            next_status_index = (current_status_index + 1) % len(ORDER_STATUSES)
            new_status = ORDER_STATUSES[next_status_index]
            
            # Обновляем статус в заказе
            orders[order_index]["status"] = new_status
            save_orders(orders)
            
            # Создаем кнопку для обновления статуса
            keyboard = [[InlineKeyboardButton("🔄 Обновить статус", callback_data=f"status_{order_number}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Формируем текст сообщения
            order_text = f"""
✅ Заказ №{order_number} оформлен!

🛒 Товар: {order['item_name']}
📁 Категория: {order['category']}
🔢 Количество: {order['quantity']} шт.
💰 Цена за единицу: ${order['price_per_unit']}
💵 Общая стоимость: ${order['total_price']}

📅 Дата заказа: {order['timestamp'][:19].replace('T', ' ')}

Текущий статус: {new_status}

Нажмите кнопку "Обновить статус" для проверки актуального статуса заказа.
            """
            
            # Пытаемся обновить сообщение
            try:
                await query.message.edit_text(order_text, reply_markup=reply_markup)
            except Exception as e:
                print(f"Ошибка при обновлении сообщения: {e}")
                # Если не можем обновить, отправляем новое сообщение
                await query.message.reply_text(order_text, reply_markup=reply_markup)
            
            return True
        else:
            await query.answer("Заказ не найден")
            return False
            
    except Exception as e:
        print(f"Ошибка в update_status_message: {e}")
        await query.answer("Ошибка при обновлении статуса")
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'Каталог':
        await show_categories(update, context)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Всегда отвечаем на callback
    
    data = query.data
    
    if data.startswith('cat_'):
        category_key = data.split('_')[1]
        # Показываем товары выбранной категории
        await show_products(update, context, category_key)
        
    elif data.startswith('item_'):
        item_id = data.split('_')[1]
        # Сохраняем выбранный товар в контексте
        context.user_data['selected_item'] = item_id
        context.user_data['current_quantity'] = ""  # Инициализируем количество
        # Показываем цифровую клавиатуру
        await show_quantity_keyboard(query, item_id)
        
    elif data.startswith('qty_'):
        # Обработка нажатий на цифровую клавиатуру
        parts = data.split('_')
        action = parts[1]
        item_id = parts[2]
        
        if action == 'enter':
            # Подтверждение ввода количества
            current_quantity = context.user_data.get('current_quantity', '')
            if not current_quantity or current_quantity == '':
                current_quantity = '0'
            
            try:
                quantity = int(current_quantity)
                if quantity <= 0:
                    await query.answer("Количество должно быть больше 0!")
                    return
                
                # Обрабатываем заказ (как раньше)
                await process_order_with_quantity(query, context, item_id, quantity)
                
            except ValueError:
                await query.answer("Введите корректное число!")
                return
                
        elif action == 'backspace':
            # Удалить последний символ
            current_quantity = context.user_data.get('current_quantity', '')
            if current_quantity:
                new_quantity = current_quantity[:-1]
                context.user_data['current_quantity'] = new_quantity
                await update_quantity_display(query, new_quantity, item_id)
            else:
                await query.answer("Пусто")
                
        elif action == 'clear':
            # Стереть всё
            context.user_data['current_quantity'] = ""
            await update_quantity_display(query, "", item_id)
            await query.answer("Очищено")
                
        else:
            # Добавляем цифру к текущему количеству
            digit = action
            current_quantity = context.user_data.get('current_quantity', '')
            new_quantity = current_quantity + digit
            
            # Ограничиваем длину (например, максимум 5 цифр)
            if len(new_quantity) <= 5:
                context.user_data['current_quantity'] = new_quantity
                await update_quantity_display(query, new_quantity, item_id)
            else:
                await query.answer("Слишком большое число!")
        
    elif data.startswith('status_'):
        # Обновление статуса заказа
        order_number = data.split('_')[1]
        await update_status_message(query, order_number)
        
    elif data == 'back_to_categories':
        # Возвращаемся к списку категорий
        await show_categories(update, context)
    
    print(f"Получен callback: {data}")
    sys.stdout.flush()


async def process_order_with_quantity(query, context, item_id, quantity):
    """Обработка заказа с заданным количеством"""
    try:
        # Получаем информацию о товаре
        products = load_products()
        
        # Ищем товар во всех категориях
        item_data = None
        category_name = ""
        for category_key, category_data in products.items():
            if item_id in category_data['items']:
                item_data = category_data['items'][item_id]
                category_name = category_data['name']
                break
        
        if not item_data:
            await query.message.edit_text("Ошибка: товар не найден")
            return
        
        # Рассчитываем общую стоимость
        total_price = item_data['price'] * quantity
        
        # Создаем заказ
        order_data = {
            "user_id": query.from_user.id,
            "username": query.from_user.username,
            "item_id": item_id,
            "item_name": item_data['name'],
            "category": category_name,
            "quantity": quantity,
            "price_per_unit": item_data['price'],
            "total_price": total_price,
            "timestamp": datetime.now().isoformat()
        }
        
        # Сохраняем заказ
        order = create_order(order_data)
        
        # Отправляем подтверждение с кнопкой обновления статуса
        order_number = order["order_number"]
        
        # Создаем кнопку для обновления статуса
        keyboard = [[InlineKeyboardButton("🔄 Обновить статус", callback_data=f"status_{order_number}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Формируем текст сообщения
        order_text = f"""
✅ Заказ №{order_number} оформлен!

🛒 Товар: {item_data['name']}
📁 Категория: {category_name}
🔢 Количество: {quantity} шт.
💰 Цена за единицу: ${item_data['price']}
💵 Общая стоимость: ${total_price}

📅 Дата заказа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Текущий статус: {order['status']}

Нажмите кнопку "Обновить статус" для проверки актуального статуса заказа.
        """
        
        await query.message.edit_text(order_text, reply_markup=reply_markup)
        
        # Очищаем контекст
        if 'selected_item' in context.user_data:
            del context.user_data['selected_item']
        if 'current_quantity' in context.user_data:
            del context.user_data['current_quantity']
            
    except Exception as e:
        print(f"Ошибка при обработке заказа: {e}")
        await query.message.edit_text("Произошла ошибка при оформлении заказа. Попробуйте еще раз.")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    # Обычная обработка сообщений
    if update.message.text == 'Каталог':
        await show_categories(update, context)
    else:
        # Игнорируем текстовые сообщения, кроме кнопки Каталог
        pass

async def post_init(application):
    """Выполняется после инициализации бота"""
    await set_commands(application)

def main():
    
    print("🤖 Бот запущен! Отправь команду /start в Telegram.")
    sys.stdout.flush()
    
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    # Обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalog", catalog))
    app.add_handler(CommandHandler("orders", my_orders))
    app.add_handler(CommandHandler("help", help_command))
    
    # Обработчик callback-запросов от inline-кнопок
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Обработчик текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
