import os
import json
import base64
import logging
import datetime
from aiogram import Bot, Dispatcher, executor, types
import gspread
from google.oauth2.service_account import Credentials
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
import csv

# Load config from env
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
GOOGLE_CREDS_BASE64 = os.getenv('GOOGLE_CREDS_BASE64')

# Admin usernames
ADMINS = ['NadyaOva', 'cinichenko']

# Logging
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Get bot info
BOT_USERNAME = None

async def setup_bot_username():
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username

# Google Sheets setup
if not GOOGLE_CREDS_BASE64:
    raise ValueError("❌ GOOGLE_CREDS_BASE64 is not set. Check your Railway Variables.")

creds_dict = json.loads(base64.b64decode(GOOGLE_CREDS_BASE64))
credentials = Credentials.from_service_account_info(creds_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"])
client = gspread.authorize(credentials)
sheet = client.open_by_key(SPREADSHEET_ID)
users_sheet = sheet.worksheet("users")
log_sheet = sheet.worksheet("log")

def log_action(user_id, username, action, details=''):
    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    log_sheet.append_row([timestamp, user_id, username, action, details])

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
            log_action(user_id, "", "Wallet updated", wallet)
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

def get_referral_count(referrer_id):
    records = users_sheet.get_all_records()
    return sum(1 for r in records if str(r.get('referrer_id')) == str(referrer_id))

welcome_keyboard = InlineKeyboardMarkup(row_width=2).add(
    InlineKeyboardButton("\ud83d\udcec Invite Friends", callback_data="invite"),
    InlineKeyboardButton("\ud83d\udce5 Submit Wallet", callback_data="wallet"),
    InlineKeyboardButton("\ud83d\ude80 About MarsUnity", callback_data="about"),
    InlineKeyboardButton("\ud83d\udcb1 How to Buy", callback_data="buy"),
)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username or ''

    if not await is_subscribed(user_id):
        await message.answer("\ud83d\udc40 Please subscribe to @marsunity42 and then type /start again.")
        return

    args = message.get_args()
    referrer_id = args if args.isdigit() else ''

    if not is_registered(user_id):
        users_sheet.append_row([user_id, username, '', referrer_id])
        log_action(user_id, username, "Registered", f"Referred by: {referrer_id if referrer_id else 'None'}")

    await message.answer(
        "\ud83d\ude80 <b>Welcome to the MarsUnity Airdrop!</b>\n\n"
        "Complete these tasks to join the airdrop:\n\n"
        "1. Follow us on <a href=\"https://x.com/MarsUnity42\">Twitter</a>\n"
        "2. Join our <a href=\"https://t.me/marsunity42\">Telegram</a>\n"
        "3. Invite friends (see button below)\n"
        "4. Submit your Solana wallet address (starting with 5...)\n\n"
        "To participate, you <b>must</b>:\n"
        "- Be subscribed to @marsunity42\n"
        "- Provide a valid Solana address\n\n"
        "Use the buttons below to continue:",
        parse_mode='HTML',
        reply_markup=welcome_keyboard
    )

@dp.callback_query_handler(lambda c: c.data == 'invite')
async def handle_invite(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    referral_link = f"https://t.me/{BOT_USERNAME}?start={callback_query.from_user.id}"
    await bot.send_message(callback_query.from_user.id,
        f"\ud83d\ude80 Invite your friends to join MarsUnity and receive cosmic karma:\n\n"
        f"<b>Join MarsUnity</b> — the meme token with purpose!\n\n"
        f"Your invite link:\n{referral_link}",
        parse_mode="HTML")

# (остальной код остаётся без изменений)

if __name__ == '__main__':
    from asyncio import get_event_loop
    loop = get_event_loop()
    loop.run_until_complete(setup_bot_username())
    executor.start_polling(dp, skip_updates=True)
