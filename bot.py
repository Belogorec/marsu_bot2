import os
print(f"GOOGLE_CREDS_BASE64 exists? {bool(os.getenv('GOOGLE_CREDS_BASE64'))}")
import os
import logging
import base64
import json

from aiogram import Bot, Dispatcher, executor, types
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Logging
logging.basicConfig(level=logging.INFO)

# Telegram config
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
GOOGLE_CREDS_BASE64 = os.getenv('GOOGLE_CREDS_BASE64')

# Telegram
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(base64.b64decode(GOOGLE_CREDS_BASE64))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Проверка подписки
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.warning(f"[ERROR] Subscription check failed: {e}")
        return False

# Проверка регистрации
def is_registered(user_id):
    records = sheet.get_all_records()
    return any(str(r['user_id']) == str(user_id) for r in records)

# Обновление кошелька
def update_wallet(user_id, wallet):
    cell = sheet.find(str(user_id))
    if cell:
        row = cell.row
        if sheet.cell(row, 3).value == '':
            sheet.update_cell(row, 3, wallet)
            return True
    return False

# /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username or ''

    if not await is_subscribed(user_id):
        await message.answer(f"🚨 To participate in the Airdrop, please subscribe to our channel: https://t.me/{CHANNEL_USERNAME}\nThen click /start again.")
        return

    if is_registered(user_id):
        await message.answer("✅ You're already participating in the Airdrop!\n\nTo check your status, type /status.")
        return

    sheet.append_row([user_id, username, ''])
    await message.answer("🎉 You're successfully registered!\n\nNow send your **SOLANA wallet address** (only once, starting with `5...`).")

# Сохранение кошелька
@dp.message_handler(lambda message: message.chat.type == 'private' and message.text.startswith('5') and len(message.text.strip()) > 20)
async def save_wallet(message: types.Message):
    user_id = message.from_user.id
    wallet = message.text.strip()

    if update_wallet(user_id, wallet):
        await message.answer("💾 Wallet saved successfully!\nYou're now fully registered in the Airdrop.")
    else:
        await message.answer("😅 You already submitted a wallet or haven’t started yet. Type /start to begin.")

# /status
@dp.message_handler(commands=['status'])
async def status(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = str(message.from_user.id)
    records = sheet.get_all_records()
    for r in records:
        if str(r['user_id']) == user_id:
            wallet = r['wallet'] if r['wallet'] else "(not provided)"
            await message.answer(f"📋 Your Airdrop status:\n\n🔹 Wallet: `{wallet}`", parse_mode="Markdown")
            return
    await message.answer("🙈 You're not registered yet.\nType /start to join the Airdrop.")

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=False)
