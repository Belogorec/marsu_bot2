import os
import logging
from aiogram import Bot, Dispatcher, executor, types
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Telegram config
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# Logging
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("google_creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# --- Helpers --- #
async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.warning(f"[ERROR] Subscription check failed: {e}")
        return False

def is_registered(user_id):
    records = sheet.get_all_records()
    return any(str(r['user_id']) == str(user_id) for r in records)

def update_wallet(user_id, wallet):
    cell = sheet.find(str(user_id))
    if cell:
        row = cell.row
        if sheet.cell(row, 3).value == '':
            sheet.update_cell(row, 3, wallet)
            return True
    return False

# --- Handlers --- #
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username or ''

    if not await is_subscribed(user_id):
        await message.answer(
            "🛰 To join the Airdrop, first subscribe to our channel:\n"
            f"👉 https://t.me/{CHANNEL_USERNAME}\n\n"
            "Then come back and press /start again."
        )
        return

    if is_registered(user_id):
        await message.answer(
            "🚀 You're already aboard!\n"
            "Want to check your status? Just type /status."
        )
        return

    sheet.append_row([user_id, username, ''])
    await message.answer(
        "✅ You're officially in!\n"
        "Now send your **SOLANA wallet address** (just once, no edits).\n"
        "We'll link it to your Airdrop participation."
    )

@dp.message_handler(lambda message: message.chat.type == 'private' and message.text.startswith('5') and len(message.text.strip()) > 20)
async def save_wallet(message: types.Message):
    user_id = message.from_user.id
    wallet = message.text.strip()

    if update_wallet(user_id, wallet):
        await message.answer("📡 Wallet received and saved!\nYou're all set. Airdrop transmission initiated 👨‍🚀")
    else:
        await message.answer(
            "⚠️ Hmm... Something's off.\n"
            "Either you've already submitted a wallet, or you haven't registered yet.\n\n"
            "Start with /start and make sure you follow the instructions carefully."
        )

@dp.message_handler(commands=['status'])
async def status(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = str(message.from_user.id)
    records = sheet.get_all_records()
    for r in records:
        if str(r['user_id']) == user_id:
            wallet = r['wallet'] if r['wallet'] else "(not provided)"
            await message.answer(f"📊 Airdrop Status:\nSOLANA Wallet → `{wallet}`", parse_mode="Markdown")
            return
    await message.answer("🔍 No record found.\nSend /start to register for the Airdrop mission.")

@dp.message_handler(commands=['ping'])
async def ping(message: types.Message):
    await message.answer("✅ I'm online and ready for launch 🚀")

# --- Run --- #
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=False)
