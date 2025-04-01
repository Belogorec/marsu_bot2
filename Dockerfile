
FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

ENV API_TOKEN=${API_TOKEN}
ENV CHANNEL_USERNAME=${CHANNEL_USERNAME}
ENV SPREADSHEET_ID=${SPREADSHEET_ID}

CMD ["python", "bot.py"]
