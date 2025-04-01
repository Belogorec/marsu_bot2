import os
import json
import base64
import logging
from aiogram import Bot, Dispatcher, executor, types
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Конфигурация
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')  # без @
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
GOOGLE_CREDS_BASE64 = os.getenv('GOOGLE_CREDS_BASE64')
NOTIFY_CHANNEL = '@marsunity42'

logging.basicConfig(level=logging.INFO)

# Telegram bot
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Подключение к Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(base64.b64decode(GOOGLE_CREDS_BASE64))
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# Рабочие листы
sheet = client.open_by_key(SPREADSHEET_ID)
users_ws = sheet.worksheet("users")
log_ws = sheet.worksheet("log")

# Лог действий
def log_action(user_id, username, action, details=''):
    log_ws.append_row([
        str(datetime.now()), str(user_id), username or '', action, details
    ])

# Проверка подписки
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id='@' + CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.warning(f"[Subscription check failed] {e}")
        return False

# Проверка участия
def is_registered(user_id):
    records = users_ws.get_all_records()
    return any(str(r['user_id']) == str(user_id) for r in records)

# Обновление кошелька
def update_wallet(user_id, wallet):
    try:
        cell = users_ws.find(str(user_id))
        if cell:
            row = cell.row
            if users_ws.cell(row, 3).value == '':
                users_ws.update_cell(row, 3, wallet)
                return True
    except Exception as e:
        logging.warning(f"[Wallet update error] {e}")
    return False

# --- Обработчики --- #

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username or ''

    if not await is_subscribed(user_id):
        await message.answer(f'📢 Please subscribe to @{CHANNEL_USERNAME} and then press /start again.')
        return

    if is_registered(user_id):
        await message.answer("😎 You're already participating in the Airdrop!\n\nType /status to check your wallet.")
        return

    # Кнопка подтверждения
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("✅ Confirm participation", callback_data="confirm_join"))
    await message.answer("🎯 You're subscribed! Tap below to confirm participation:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == "confirm_join")
async def process_confirmation(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    user_id = user.id
    username = user.username or ''

    if is_registered(user_id):
        await callback_query.message.edit_text("✅ You already confirmed your participation!")
        return

    users_ws.append_row([user_id, username, ''])
    log_action(user_id, username, 'Registered')
    await callback_query.message.edit_text("🎉 You're registered!\n\nNow send your SOLANA wallet address (starting with 5...).")
    await bot.send_message(NOTIFY_CHANNEL, f"📥 New participant: @{username} (ID: {user_id})")

@dp.message_handler(commands=['status'])
async def check_status(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = str(message.from_user.id)
    records = users_ws.get_all_records()
    for r in records:
        if str(r['user_id']) == user_id:
            wallet = r['wallet'] if r['wallet'] else "(not provided)"
            await message.answer(f"📋 Your Airdrop status:\n\n🔹 Wallet: {wallet}")
            return
    await message.answer("🤖 You’re not registered yet. Type /start to begin.")

@dp.message_handler(lambda message: message.chat.type == 'private' and message.text.startswith('5') and len(message.text.strip()) > 20)
async def receive_wallet(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ''
    wallet = message.text.strip()

    if update_wallet(user_id, wallet):
        log_action(user_id, username, 'Wallet submitted', wallet)
        await message.answer("✅ Wallet saved. Thanks for participating!")
    else:
        await message.answer("😅 You already submitted a wallet or haven’t started yet. Type /start to begin.")

# --- Запуск бота --- #
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=False)
