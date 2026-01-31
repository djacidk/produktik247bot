from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import Update
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import json
import logging
import sys
import io
from datetime import datetime
from dotenv import load_dotenv
import os
import asyncio
import threading
from contextlib import asynccontextmanager

# Загружаем переменные из файла .env
load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    exit("Ошибка: TOKEN не найден в переменной окружении!")

DOMAIN = os.getenv("DOMAIN")
if not DOMAIN:
    exit("Ошибка: DOMAIN не найден в переменной окружении!")

PORT = int(os.getenv("PORT", 8000))

# Исправляем кодировку для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- WEBHOOK НАСТРОЙКИ ---
WEBHOOK_URL = f'https://{DOMAIN}/{TOKEN}'

# Инициализируем бота и диспетчер
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
router = Router()

# --- LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 Запуск на Webhook: {WEBHOOK_URL}")
    await set_webhook()
    print("✅ Telegram бот запущен на Webhook")
    sys.stdout.flush()
    yield
    # Shutdown
    await bot.session.close()

# FastAPI приложение
app = FastAPI(lifespan=lifespan)

# Добавляем CORS middleware для Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все источники для Mini App
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Список возможных статусов
ORDER_STATUSES = ["Собирается", "Готовится", "Отправлен", "Доставлен"]

# Потокобезопасное хранилище количеств
quantities_storage = {}
quantities_lock = threading.Lock()

# --- РАБОТА С ДАННЫМИ ---
def load_products():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Файл products.json не найден!")
        return {}

def load_orders():
    try:
        with open('orders.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Файл orders.json не найден!")
        return []

def save_orders(orders):
    try:
        with open('orders.json', 'w', encoding='utf-8') as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка при сохранении orders.json: {e}")
        import traceback
        traceback.print_exc()

def create_order(order_data):
    orders = load_orders()
    order_number = len(orders) + 1
    
    # Проверяем, есть ли в данных массив items (множественные товары)
    if "items" in order_data:
        # Создаем один заказ с массивом товаров
        new_order = {
            "order_number": order_number,
            "user_id": order_data["user_id"],
            "username": order_data["username"],
            "items": order_data["items"],
            "total_price": order_data["total_price"],
            "timestamp": order_data["timestamp"],
            "status": "Собирается"
        }
    else:
        # Старый формат с одним товаром
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
            "status": "Собирается"
        }
    
    orders.append(new_order)
    save_orders(orders)
    return new_order

# --- WEBHOOK SETUP ---
async def set_webhook():
    """Устанавливает webhook в Telegram"""
    try:
        await bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Webhook успешно установлен: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Ошибка установки Webhook: {e}")
    sys.stdout.flush()

# --- КОМАНДЫ ---
@router.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    # Передаём user_id и username как параметры URL
    mini_app_url = f"https://{DOMAIN}/app?user_id={user_id}&username={username}"
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="🛍️ Открыть магазин",
                web_app=types.WebAppInfo(url=mini_app_url)
            )],
            [types.InlineKeyboardButton(
                text="📋 Мои заказы",
                callback_data="orders"
            )]
        ]
    )
    
    welcome_text = """
🤖 Добро пожаловать в магазин продуктов!

🛒 Нажмите кнопку ниже, чтобы открыть магазин в удобном интерфейсе.

Доступные команды:
/start - Запустить бота
/orders - Просмотреть ваши заказы
/help - Помощь
    """
    
    await message.reply(welcome_text, reply_markup=keyboard)



@router.message(Command("orders"))
async def my_orders(message: types.Message):
    """Показать список заказов пользователя"""
    user_id = message.from_user.id
    orders = load_orders()
    
    user_orders = [order for order in orders if order["user_id"] == user_id and order["status"] != "Доставлен"]
    
    if not user_orders:
        await message.reply("У вас пока нет заказов.")
        return
    
    orders_text = "📋 Ваши заказы:\n\n"
    for order in reversed(user_orders[-10:]):
        # Проверяем, есть ли в заказе массив items (множественные товары)
        if "items" in order:
            # Новый формат с множественными товарами
            items_count = len(order["items"])
            items_text = f"{items_count} товар{'ов' if items_count > 1 else ''}"
            orders_text += f"№{order['order_number']} - {items_text}\n"
        else:
            # Старый формат с одним товаром
            orders_text += f"№{order['order_number']} - {order['item_name']} ({order['quantity']} шт.)\n"
        
        orders_text += f"Статус: {order['status']}\n"
        orders_text += f"Стоимость: ${order['total_price']}\n"
        orders_text += "➖➖➖\n"
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="🔄 Обновить статус",
                callback_data="orders"
            )]
        ]
    )
    
    await message.reply(orders_text, reply_markup=keyboard)

@router.message(Command("help"))
async def help_command(message: types.Message):
    help_text = """
🤖 Доступные команды:
/start - Запустить бота
/orders - Просмотреть ваши заказы
/help - Показать помощь

🛒 Чтобы сделать заказ:
1. Откройте магазин через кнопку в /start
2. Выберите товары и добавьте их в корзину
3. Оформите заказ через корзину
    """
    await message.reply(help_text)





# --- ТОВАРЫ ---
async def show_products_cb(query: types.CallbackQuery, category_key: str):
    """Показывает товары выбранной категории"""
    products = load_products()
    
    if category_key not in products:
        await query.answer("Категория не найдена")
        return
    
    category_data = products[category_key]
    items = category_data.get('items', {})
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text=f"{item_data['name']} - ${item_data['price']}",
                callback_data=f"item_{item_id}"
            )]
            for item_id, item_data in items.items()
        ] + [
            [types.InlineKeyboardButton(
                text="🔙 Назад к категориям",
                callback_data="back_to_categories"
            )]
        ]
    )
    
    message_text = f"🛒 Товары в категории '{category_data['name']}':"
    
    try:
        await query.message.edit_text(message_text, reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка при обновлении товаров: {e}")
    
    await query.answer()



# --- ОБНОВЛЕНИЕ СТАТУСА ---
async def update_status_message(query: types.CallbackQuery, order_number: str):
    """Обновление сообщения со статусом заказа"""
    try:
        orders = load_orders()
        
        order = None
        order_index = None
        for i, o in enumerate(orders):
            if str(o["order_number"]) == order_number:
                order = o
                order_index = i
                break
        
        if order and order_index is not None:
            current_status_index = ORDER_STATUSES.index(order["status"])
            next_status_index = (current_status_index + 1) % len(ORDER_STATUSES)
            new_status = ORDER_STATUSES[next_status_index]
            
            orders[order_index]["status"] = new_status
            save_orders(orders)
            
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(
                    text="🔄 Обновить статус",
                    callback_data=f"status_{order_number}"
                )]]
            )
            
            # Проверяем, есть ли в заказе массив items (множественные товары)
            if "items" in order:
                # Новый формат с множественными товарами
                items_text = "\n".join([
                    f"  • {item['item_name']} ({item['quantity']} шт.) - ${item['total_price']}"
                    for item in order["items"]
                ])
                
                order_text = f"""
✅ Заказ №{order_number} оформлен!

🛒 Товары:
{items_text}

💵 Общая стоимость: ${order['total_price']}

📅 Дата заказа: {order['timestamp'][:19].replace('T', ' ')}

Текущий статус: {new_status}

Нажмите кнопку "Обновить статус" для проверки актуального статуса заказа.
                """
            else:
                # Старый формат с одним товаром
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
            
            try:
                await query.message.edit_text(order_text, reply_markup=keyboard)
            except Exception as e:
                print(f"Ошибка при обновлении сообщения: {e}")
                await query.message.reply(order_text, reply_markup=keyboard)
            
            return True
        else:
            await query.answer("Заказ не найден")
            return False
            
    except Exception as e:
        print(f"Ошибка в update_status_message: {e}")
        await query.answer("Ошибка при обновлении статуса")
        return False

# --- ОБРАБОТКА ЗАКАЗА ---






@router.callback_query(F.data.startswith("status_"))
async def callback_status(query: types.CallbackQuery):
    order_number = query.data.split('_')[1]
    await update_status_message(query, order_number)



@router.callback_query(F.data == "orders")
async def callback_orders(query: types.CallbackQuery):
    """Показать заказы пользователя"""
    user_id = query.from_user.id
    orders = load_orders()
    
    user_orders = [order for order in orders if order["user_id"] == user_id and order["status"] != "Доставлен"]
    
    if not user_orders:
        await query.answer("У вас пока нет заказов")
        return
    
    orders_text = "📋 Ваши заказы:\n\n"
    for order in reversed(user_orders[-5:]):
        # Проверяем, есть ли в заказе массив items (множественные товары)
        if "items" in order:
            # Новый формат с множественными товарами
            items_count = len(order["items"])
            items_text = f"{items_count} товар{'ов' if items_count > 1 else ''}"
            orders_text += f"№{order['order_number']} - {items_text}\n"
        else:
            # Старый формат с одним товаром
            orders_text += f"№{order['order_number']} - {order['item_name']} ({order['quantity']} шт.)\n"
        
        orders_text += f"Статус: {order['status']}\n"
        orders_text += f"Стоимость: ${order['total_price']}\n"
        orders_text += "➖➖➖\n"
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="🔄 Обновить статус",
                callback_data="orders"
            )]
        ]
    )
    
    await query.answer()
    await query.message.answer(orders_text, reply_markup=keyboard)

# Добавляем роутер в диспетчер
dp.include_router(router)

# --- WEBHOOK ENDPOINT ---
@app.post(f"/{TOKEN}")
async def webhook(request: Request):
    update_data = await request.json()
    update = Update(**update_data)
    asyncio.create_task(dp.feed_update(bot, update))
    return {"ok": True}

# --- MINI APP API ENDPOINTS ---
@app.get("/api/products")
async def get_products():
    """API для получения товаров для Mini App"""
    try:
        products = load_products()
        return products
    except Exception as e:
        print(f"❌ Ошибка загрузки товаров: {e}")
        return {"error": str(e)}, 500

@app.post("/api/order")
async def create_order_api(request: Request):
    """API для создания заказа из Mini App"""
    try:
        order_data_raw = await request.json()
        
        # Поддержка обоих форматов: с items (множественные товары) и без (один товар)
        if "items" in order_data_raw:
            # Новый формат с множественными товарами
            order_data = {
                "user_id": order_data_raw.get("user_id", 0),
                "username": order_data_raw.get("username", "unknown"),
                "items": order_data_raw.get("items"),
                "total_price": order_data_raw.get("total_price"),
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Старый формат с одним товаром (для обратной совместимости)
            order_data = {
                "user_id": order_data_raw.get("user_id", 0),
                "username": order_data_raw.get("username", "unknown"),
                "item_id": order_data_raw.get("item_id"),
                "item_name": order_data_raw.get("item_name"),
                "category": order_data_raw.get("category"),
                "quantity": order_data_raw.get("quantity"),
                "price_per_unit": order_data_raw.get("price_per_unit"),
                "total_price": order_data_raw.get("total_price"),
                "timestamp": datetime.now().isoformat()
            }
        
        order = create_order(order_data)
        
        return {
            "order_number": order["order_number"],
            "total_price": order["total_price"],
            "status": order["status"]
        }
        
    except Exception as e:
        print(f"❌ Ошибка при создании заказа: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

# --- ADMIN API ENDPOINTS ---
@app.get("/api/admin/orders")
async def get_admin_orders():
    """API для получения всех заказов (для админ-панели)"""
    try:
        orders = load_orders()
        return orders
    except Exception as e:
        print(f"❌ Ошибка загрузки заказов: {e}")
        return {"error": str(e)}, 500

@app.post("/api/admin/order/status")
async def update_order_status(request: Request):
    """API для обновления статуса заказа"""
    try:
        data = await request.json()
        order_number = data.get("order_number")
        new_status = data.get("status")
        
        if not order_number or not new_status:
            return {"error": "order_number and status are required"}, 400
        
        if new_status not in ORDER_STATUSES:
            return {"error": f"Invalid status. Valid values: {ORDER_STATUSES}"}, 400
        
        orders = load_orders()
        
        order_index = None
        for i, order in enumerate(orders):
            if order["order_number"] == order_number:
                order_index = i
                break
        
        if order_index is None:
            return {"error": "Order not found"}, 404
        
        orders[order_index]["status"] = new_status
        save_orders(orders)
        
        return {
            "order_number": order_number,
            "status": new_status,
            "success": True
        }
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении статуса: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500

@app.get("/admin")
async def serve_admin_app():
    """Служит админ-панель"""
    try:
        with open("admin_app.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        return HTMLResponse(
            content=html_content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except FileNotFoundError:
        return {"error": "admin_app.html not found"}, 404

# --- STATIC ФАЙЛЫ ---
@app.get("/app")
async def serve_mini_app():
    """Служит Mini App HTML без кэширования"""
    try:
        with open("mini_app.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        return HTMLResponse(
            content=html_content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except FileNotFoundError:
        return {"error": "mini_app.html not found"}, 404

@app.get("/")
async def root():
    """Главная страница"""
    return {"message": "Telegram Bot API", "app": "https://your-domain/app"}

if __name__ == "__main__":
    uvicorn.run(
        "simple_bot_aiogram:app",
        host="0.0.0.0",
        port=PORT,
        ssl_keyfile="privkey.pem",
        ssl_certfile="fullchain.pem",
        log_level="error"
    )
