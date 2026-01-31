from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging
import sys
import io
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    force=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главное меню с выбором метода ввода"""
    keyboard = [
        ['1. Текстовый ввод'],
        ['2. ReplyKeyboard (кнопки под вводом)'],
        ['3. Inline кнопки (в сообщении)']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🧪 Тестирование методов ввода данных\n\n"
        "Выберите метод ввода:",
        reply_markup=reply_markup
    )

# ==================== МЕТОД 1: ТЕКСТОВЫЙ ВВОД ====================
async def text_input_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Демонстрация текстового ввода"""
    context.user_data['demo_mode'] = 'text'
    context.user_data['quantity'] = ""
    
    await update.message.reply_text(
        "📝 ТЕКСТОВЫЙ ВВОД\n\n"
        "Введите количество числом (например: 5)\n"
        "Или введите 'меню' для возврата"
    )

# ==================== МЕТОД 2: REPLY KEYBOARD ====================
async def reply_keyboard_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Демонстрация ReplyKeyboard"""
    context.user_data['demo_mode'] = 'reply'
    context.user_data['quantity'] = ""
    
    # Создаем цифровую клавиатуру
    keyboard = [
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9'],
        ['0', '⌫', '✅ Готово'],
        ['❌ Очистить', '🏠 Меню']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🔢 REPLY KEYBOARD (кнопки под полем ввода)\n\n"
        "Используйте кнопки для ввода количества:",
        reply_markup=reply_markup
    )
    await update.message.reply_text("Текущее количество: 0")

# ==================== МЕТОД 3: INLINE KEYBOARD ====================
async def inline_keyboard_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Демонстрация InlineKeyboard"""
    context.user_data['demo_mode'] = 'inline'
    context.user_data['quantity'] = ""
    
    # Создаем inline клавиатуру
    keyboard = [
        [InlineKeyboardButton("1", callback_data="digit_1"),
         InlineKeyboardButton("2", callback_data="digit_2"),
         InlineKeyboardButton("3", callback_data="digit_3")],
        [InlineKeyboardButton("4", callback_data="digit_4"),
         InlineKeyboardButton("5", callback_data="digit_5"),
         InlineKeyboardButton("6", callback_data="digit_6")],
        [InlineKeyboardButton("7", callback_data="digit_7"),
         InlineKeyboardButton("8", callback_data="digit_8"),
         InlineKeyboardButton("9", callback_data="digit_9")],
        [InlineKeyboardButton("0", callback_data="digit_0"),
         InlineKeyboardButton("⌫", callback_data="backspace"),
         InlineKeyboardButton("✅", callback_data="enter")],
        [InlineKeyboardButton("❌ Очистить", callback_data="clear"),
         InlineKeyboardButton("🏠 Меню", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🖱 INLINE KEYBOARD (кнопки в сообщении)\n\n"
        "Текущее количество: 0",
        reply_markup=reply_markup
    )

# ==================== ОБРАБОТЧИКИ ====================
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    
    # Навигация по меню
    if text in ['1. Текстовый ввод', '1']:
        await text_input_demo(update, context)
        return
    elif text in ['2. ReplyKeyboard (кнопки под вводом)', '2']:
        await reply_keyboard_demo(update, context)
        return
    elif text in ['3. InlineKeyboard (в сообщении)', '3']:
        await inline_keyboard_demo(update, context)
        return
    elif text == '🏠 Меню':
        await start(update, context)
        return
    
    # Обработка ввода в зависимости от режима
    demo_mode = context.user_data.get('demo_mode', '')
    
    if demo_mode == 'text':
        # Обработка текстового ввода
        try:
            quantity = int(text)
            if quantity > 0:
                await update.message.reply_text(f"✅ Принято количество: {quantity}")
                await update.message.reply_text("Введите другое число или 'меню' для возврата")
            else:
                await update.message.reply_text("❌ Количество должно быть больше 0")
        except ValueError:
            if text.lower() == 'меню':
                await start(update, context)
            else:
                await update.message.reply_text("❌ Введите число или 'меню'")
                
    elif demo_mode == 'reply':
        # Обработка ReplyKeyboard кнопок
        if text == '✅ Готово':
            current_qty = context.user_data.get('quantity', '')
            if current_qty and int(current_qty) > 0:
                await update.message.reply_text(f"✅ Принято количество: {current_qty}")
            else:
                await update.message.reply_text("❌ Введите количество больше 0")
                
        elif text == '⌫':
            current_qty = context.user_data.get('quantity', '')
            if current_qty:
                new_qty = current_qty[:-1]
                context.user_data['quantity'] = new_qty
                await update.message.reply_text(f"Текущее количество: {new_qty if new_qty else '0'}")
                
        elif text == '❌ Очистить':
            context.user_data['quantity'] = ""
            await update.message.reply_text("Текущее количество: 0")
            
        elif text.isdigit():
            current_qty = context.user_data.get('quantity', '')
            new_qty = current_qty + text
            if len(new_qty) <= 5:
                context.user_data['quantity'] = new_qty
                await update.message.reply_text(f"Текущее количество: {new_qty}")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline кнопок"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == 'menu':
        await start(update, context)
        return
    
    if data.startswith('digit_'):
        digit = data.split('_')[1]
        current_qty = context.user_data.get('quantity', '')
        new_qty = current_qty + digit
        if len(new_qty) <= 5:
            context.user_data['quantity'] = new_qty
            # Обновляем сообщение с текущим количеством
            await query.edit_message_text(
                f"🖱 INLINE KEYBOARD\n\nТекущее количество: {new_qty}",
                reply_markup=query.message.reply_markup
            )
            
    elif data == 'backspace':
        current_qty = context.user_data.get('quantity', '')
        if current_qty:
            new_qty = current_qty[:-1]
            context.user_data['quantity'] = new_qty
            await query.edit_message_text(
                f"🖱 INLINE KEYBOARD\n\nТекущее количество: {new_qty if new_qty else '0'}",
                reply_markup=query.message.reply_markup
            )
            
    elif data == 'clear':
        context.user_data['quantity'] = ""
        await query.edit_message_text(
            "🖱 INLINE KEYBOARD\n\nТекущее количество: 0",
            reply_markup=query.message.reply_markup
        )
        
    elif data == 'enter':
        current_qty = context.user_data.get('quantity', '')
        if current_qty and int(current_qty) > 0:
            await query.edit_message_text(f"✅ Принято количество: {current_qty}")
        else:
            await query.answer("❌ Введите количество больше 0!")

def main():
    
    print("🧪 Тестовый бот запущен! Отправь /start в Telegram.")
    sys.stdout.flush()
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
