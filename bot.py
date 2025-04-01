import os
import json
import base64
import logging
from aiogram import Bot, Dispatcher, executor, types
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')  # без @
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
GOOGLE_CREDS_BASE64 = os.getenv('GOOGLE_CREDS_BASE64')
NOTIFY_CHANNEL = '@marsunity42'

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Telegram bot
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Google Sheets
creds_dict = json.loads(base64.b64decode(GOOGLE_CREDS_BASE64))
creds = Credentials.from_service_account_info(creds_dict)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID)
users_ws = sheet.worksheet("users")
log_ws = sheet.worksheet("log")

def log_action(user_id, username, action, details=''):
    log_ws.append_row([
        str(datetime.now()), str(user_id), username or '', action, details
    ])

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id='@' + CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.warning(f"[Subscription check failed] {e}")
        return False

def is_registered(user_id):
    records = users_ws.get_all_records()
    return any(str(r['user_id']) == str(user_id) for r in records)

def update_wallet(user_id, wallet):
    cell = users_ws.find(str(user_id))
    if cell:
        row = cell.row
        if users_ws.cell(row, 3).value == '':
            users_ws.update_cell(row, 3, wallet)
            return True
    return False

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username or ''

    if not await is_subscribed(user_id):
        await message.answer("📢 Please subscribe to the channel and then press /start again.")
        return

    if is_registered(user_id):
        await message.answer("😎 You're already participating in the Airdrop!\n\nTo check your status, type /status.")
        return

    users_ws.append_row([user_id, username, ''])
    log_action(user_id, username, 'Registered')
    await message.answer("🎉 You're successfully registered!\n\nNow send your **SOLANA wallet address** (only once, starting with `5...`).", parse_mode='Markdown')

    # Уведомление в канал
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
    await message.answer("🤖 You're not registered yet. Type /start to begin.")

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

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=False)
