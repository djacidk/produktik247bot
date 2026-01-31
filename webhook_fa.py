import datetime
import requests
import ssl
from fastapi import FastAPI, Request
import uvicorn
import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env в систему
load_dotenv()

# Достаем значения
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    exit("Ошибка: TOKEN не найден в переменной окружения!")

DOMAIN = os.getenv("DOMAIN")
if not DOMAIN:
    exit("Ошибка: DOMAIN не найден в переменной окружения!")

PORT = os.getenv("PORT")
if not PORT:
    exit("Ошибка: PORT не найден в переменной окружения!")

# --- НАСТРОЙКИ ---
WEBHOOK_URL = f'https://{DOMAIN}/{TOKEN}'

app = FastAPI()

def set_webhook(): 
    """Автоматическая регистрация вебхука в Telegram"""
    url = f'https://api.telegram.org/bot{TOKEN}/setWebhook'
    params = {
        'url': WEBHOOK_URL,
        #'drop_pending_updates': True # Очистит старые сообщения при перезапуске
    }
    try:
        response = requests.get(url, params=params)
        result = response.json()
        if result.get('ok'):
            print(f"✅ Webhook успешно установлен: {WEBHOOK_URL}")
        else:
            print(f"❌ Ошибка установки Webhook: {result.get('description')}")
    except Exception as e:
        print(f"📡 Ошибка сети при установке Webhook: {e}")

@app.post(f"/{TOKEN}")
async def handle_webhook(request: Request):
    # Получаем данные асинхронно
    update = await request.json()
    
    # Фиксируем время с точностью до микросекунд
    now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]

    if 'message' in update:
        msg = update['message']
        text = msg.get('text', '[не текст]')
        chat_id = msg['chat']['id']
        print(f"[{now}] 📩 От {chat_id}: {text}")
    
    # Возвращаем мгновенный ответ Telegram, чтобы освободить поток
    return {"status": "ok"}

if __name__ == "__main__":
    # Сначала ставим вебхук
    set_webhook()
    
    # Запускаем асинхронный сервер
    # Используем SSL сертификаты, которые получили через Certbot
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT, 
        ssl_keyfile="privkey.pem", 
        ssl_certfile="fullchain.pem",
        log_level="error" # Это уберет лишний мусор INFO из консоли
    )
