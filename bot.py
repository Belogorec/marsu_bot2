import os
import json
import base64
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
import gspread
from google.oauth2.service_account import Credentials

# Telegram config
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
GOOGLE_CREDS_BASE64 = os.getenv('GOOGLE_CREDS_BASE64')

# Logging
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Google Sheets setup
if not GOOGLE_CREDS_BASE64:
    raise ValueError("❌ GOOGLE_CREDS_BASE64 is not set. Check Railway Variables.")

creds_dict = json.loads(base64.b64decode(GOOGLE_CREDS_BASE64))
credentials = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
client = gspread.authorize(credentials)
sheet = client.open_by_key(SPREADSHEET_ID)
users_sheet = sheet.worksheet("users")
log_sheet = sheet.worksheet("log")

def log_action(user_id, username, action, details=""):
    log_sheet.append_row([
        datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        str(user_id),
        username,
        action,
        details
    ])

def is_registered(user_id):
    records = users_sheet.get_all_records()
    return any(str(r['user_id']) == str(user_id) for r in records)

def update_wallet(user_id, wallet):
    try:
        cell = users_sheet.find(str(user_id))
        row = cell.row
        wallet_cell = users_sheet.cell(row, 3)
        if not wallet_cell.value:
            users_sheet.update_cell(row, 3, wallet)
            log_action(user_id, "", "Wallet Updated", wallet)
            return True
    except Exception as e:
        logging.error(f"[ERROR] update_wallet: {e}")
    return False

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.warning(f"[ERROR] Subscription check failed: {e}")
        return False

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username or ''

    if not await is_subscribed(user_id):
        await message.answer(f"👀 Please subscribe to @{CHANNEL_USERNAME} and try again.")
        return

    if is_registered(user_id):
        await message.answer("😄 You're already participating! To check status, type /status.")
        return

    users_sheet.append_row([user_id, username, ''])
    log_action(user_id, username, "Registered")
    await message.answer("🎉 You're registered!\n\nNow send your SOLANA wallet address (starting with 5...).")

@dp.message_handler(lambda message: message.chat.type == 'private' and message.text.startswith('5') and len(message.text.strip()) > 20)
async def save_wallet(message: types.Message):
    user_id = message.from_user.id
    wallet = message.text.strip()

    if update_wallet(user_id, wallet):
        await message.answer("✅ Wallet saved successfully! You're all set.")
    else:
        await message.answer("😅 You already submitted a wallet or haven’t started yet. Type /start to begin.")

@dp.message_handler(commands=['status'])
async def check_status(message: types.Message):
    user_id = str(message.from_user.id)
    records = users_sheet.get_all_records()
    for r in records:
        if str(r['user_id']) == user_id:
            wallet = r['wallet'] if r['wallet'] else "(not provided)"
            await message.answer(f"📋 Your Airdrop status:\n\n🔹 Wallet: {wallet}")
            return
    await message.answer("👋 You're not registered yet. Send /start to join.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
