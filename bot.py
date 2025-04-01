
import os
import logging
from aiogram import Bot, Dispatcher, executor, types
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Telegram config
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')

# Google Sheets config
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

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
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

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username or ''

    if not await is_subscribed(user_id):
        await message.answer(f'Please subscribe to {CHANNEL_USERNAME} and try /start again.')
        return

    if is_registered(user_id):
        await message.answer("You're already participating in the Airdrop! To check your status, type /status.")
        return

    sheet.append_row([user_id, username, ''])
    await message.answer("You're successfully registered! Now please send your SOLANA wallet address (only once).")

@dp.message_handler(lambda message: message.chat.type == 'private' and message.text.startswith('5') and len(message.text.strip()) > 20)
async def save_wallet(message: types.Message):
    user_id = message.from_user.id
    wallet = message.text.strip()

    if update_wallet(user_id, wallet):
        await message.answer("✅ Wallet saved. Thanks for participating!")
    else:
        await message.answer("😅 Wallet already saved or you're not registered. Start with /start.")

@dp.message_handler(commands=['status'])
async def status(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = str(message.from_user.id)
    records = sheet.get_all_records()
    for r in records:
        if str(r['user_id']) == user_id:
            wallet = r['wallet'] if r['wallet'] else "(not provided)"
            await message.answer(f"Your Airdrop status:\nWallet: {wallet}")
            return
    await message.answer("You're not registered yet. Send /start to join.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=False)
