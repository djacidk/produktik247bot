FROM python:3.11-slim

# Устанавливаем рабочую папку
WORKDIR /app

# Копируем список зависимостей
COPY requirements.txt .

# Устанавливаем их ОДИН РАЗ при сборке образа
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код (наше приложение)
COPY . .

# Команда запуска (теперь без pip install)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]