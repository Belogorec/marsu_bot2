
import os
import logging
from aiogram import Bot, Dispatcher, executor, types
import csv

API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

CSV_FILE = 'participants.csv'
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'username', 'wallet'])

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.warning(f"Subscription check failed: {e}")
        return False

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username

    if not await is_subscribed(user_id):
        await message.answer(f'Пожалуйста, подпишись на канал {CHANNEL_USERNAME} и нажми /start снова.')
        return

    with open(CSV_FILE, 'r') as f:
        if str(user_id) in f.read():
            await message.answer("Ты уже участвуешь в Airdrop! Если хочешь проверить статус – напиши /status")
            return

    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([user_id, username, ''])

    await message.answer("Ты успешно зарегистрирован! Теперь пришли свой SOLANA-кошелёк (только один раз).")

@dp.message_handler(lambda message: message.chat.type == 'private' and message.text.startswith('5') and len(message.text.strip()) > 20)
async def save_wallet(message: types.Message):
    user_id = message.from_user.id
    wallet = message.text.strip()
    updated = False
    rows = []

    with open(CSV_FILE, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row[0] == str(user_id) and row[2] == '':
                row[2] = wallet
                updated = True
            rows.append(row)

    if updated:
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        await message.answer("✅ Кошелёк сохранён. Спасибо за участие!")
    else:
        await message.answer("😅 Кошелёк уже был сохранён или вы не зарегистрированы. Начни с /start")

@dp.message_handler(commands=['status'])
async def status(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = str(message.from_user.id)
    with open(CSV_FILE, 'r') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if row[0] == user_id:
                wallet = row[2] if row[2] else "(не указан)"
                await message.answer(f"Статус участия:\nКошелёк: {wallet}")
                return
    await message.answer("Ты ещё не участвуешь. Напиши /start")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=False)
