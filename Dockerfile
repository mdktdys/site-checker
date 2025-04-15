FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
COPY main.py .

RUN pip install --no-cache-dir -r requirements.txt

# Создаём папку для данных (на случай если её нет)
RUN mkdir -p /app/data

CMD ["python", "main.py"]
