import requests
from flask import Flask, request
import ssl
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

app = Flask(__name__)

WEBHOOK_URL = f'https://{DOMAIN}/{TOKEN}' 

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

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = request.get_json()
    if update and 'message' in update:
        msg = update['message']
        print(f"📩 [{msg['chat']['id']}] {msg.get('text', 'не текст')}")
    return 'ok', 200

if __name__ == '__main__':
    # 1. Сначала регистрируем вебхук в Telegram
    set_webhook()
    
    # 2. Затем запускаем локальный сервер
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('fullchain.pem', 'privkey.pem')
    
    print("🚀 Flask стартует...")
    app.run(host='0.0.0.0', port=PORT, ssl_context=context)
