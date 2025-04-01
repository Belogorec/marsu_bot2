FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py bot.py
COPY google_creds.json google_creds.json

CMD ["python", "bot.py"]
