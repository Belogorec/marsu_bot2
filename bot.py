import os
import json
import base64
import logging
import datetime
from aiogram import Bot, Dispatcher, executor, types
import gspread
from google.oauth2.service_account import Credentials
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import re

# Load config from env
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
GOOGLE_CREDS_BASE64 = os.getenv('GOOGLE_CREDS_BASE64')

# Admin usernames
ADMINS = ['NadyaOva', 'cinichenko']

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Get bot info
BOT_USERNAME = None

async def setup_bot_username():
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username
    logger.info(f"Bot username is @{BOT_USERNAME}")

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
    logger.info(f"Log: {user_id=} {username=} {action=} {details=}")

def is_registered(user_id):
    records = users_sheet.get_all_records()
    return any(str(r['user_id']) == str(user_id) for r in records)

def update_wallet(user_id, wallet):
    try:
        cell = users_sheet.find(str(user_id))
        row = cell.row
        current_wallet = users_sheet.cell(row, 3).value
        users_sheet.update_cell(row, 3, wallet)
        if current_wallet:
            log_action(user_id, "", "Wallet updated", wallet)
            return "updated"
        else:
            log_action(user_id, "", "Wallet saved", wallet)
            return "saved"
    except Exception as e:
        logger.error(f"[ERROR] update_wallet: {e}")
    return "error"

def validate_wallet(wallet):
    return bool(re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", wallet))

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=f"@{CHANNEL_USERNAME}", user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.warning(f"[ERROR] Subscription check failed: {e}")
        return False

def get_referral_count(referrer_id):
    records = users_sheet.get_all_records()
    return sum(1 for r in records if str(r.get('referrer_id')) == str(referrer_id))

welcome_keyboard = InlineKeyboardMarkup(row_width=2).add(
    InlineKeyboardButton("📬 Invite Friends", callback_data="invite"),
    InlineKeyboardButton("📥 Submit Wallet", callback_data="wallet"),
    InlineKeyboardButton("🚀 About MarsUnity", callback_data="about"),
    InlineKeyboardButton("💰 How to Buy", callback_data="buy"),
)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    if message.chat.type != 'private':
        return

    user_id = message.from_user.id
    username = message.from_user.username or ''

    if not await is_subscribed(user_id):
        await message.answer("👀 Please subscribe to @marsunity42 and then type /start again.")
        return

    args = message.get_args()
    referrer_id = args if args.isdigit() else ''

    if not is_registered(user_id):
        users_sheet.append_row([user_id, username, '', referrer_id])
        log_action(user_id, username, "Registered", f"Referred by: {referrer_id if referrer_id else 'None'}")

    await message.answer(
        "🚀 <b>Welcome to the MarsUnity Meme Coin AirDrop!</b> 🌌\n\n"
        "Get ready to claim your meme coin with a cosmic soul! ✨\n\n"
        "To join the fun, simply:\n\n"
        "🚀 Follow us on <a href='https://x.com/MarsUnity42'>Twitter</a>\n"
        "📡 Join our <a href='https://t.me/marsunity42'>Telegram channel</a>\n"
        "👨‍🚀 Invite your friends (use the handy button below!)\n"
        "🛸 Submit your Solana wallet address\n\n"
        "🎉 Guaranteed AirDrop for each wallet!\n\n"
        "📌 <b>Important Conditions:</b>\n"
        "- AirDrop continues until all allocated tokens are claimed.\n"
        "- Each wallet can claim tokens once—no double dips allowed!\n"
        "- We reserve the right to verify compliance with all conditions.\n\n"
        "Once all tokens designated for the AirDrop are claimed, the event will end—so hurry! 🚨✨",
        parse_mode='HTML',
        reply_markup=welcome_keyboard
    )

@dp.message_handler(commands=['status'])
async def status(message: types.Message):
    user_id = str(message.from_user.id)
    records = users_sheet.get_all_records()
    for row in records:
        if str(row['user_id']) == user_id:
            wallet = row['wallet'] if row['wallet'] else "(not provided)"
            invites = get_referral_count(user_id)
            await message.answer(
                f"📋 Your Airdrop status:\n\n"
                f"🔹 Wallet: {wallet}\n"
                f"🔸 Invites: {invites}"
            )
            return
    await message.answer("You are not registered. Please type /start to begin.")

@dp.message_handler(commands=['admin'])
async def admin_stats(message: types.Message):
    username = message.from_user.username
    if username not in ADMINS:
        await message.answer("⛔ You are not allowed to use this command.")
        return

    records = users_sheet.get_all_records()
    total = len(records)
    with_wallet = sum(1 for r in records if r.get('wallet'))
    await message.answer(f"👥 Total users: {total}\n💳 Wallets submitted: {with_wallet}")

@dp.message_handler(lambda message: message.chat.type == 'private')
async def save_wallet(message: types.Message):
    user_id = message.from_user.id
    wallet = message.text.strip()

    if validate_wallet(wallet):
        result = update_wallet(user_id, wallet)
        if result == "updated":
            await message.answer("✅ Your wallet has been updated.")
        elif result == "saved":
            await message.answer("✅ Wallet saved successfully!")
        else:
            await message.answer("⚠️ Something went wrong while saving your wallet.")
    else:
        await message.answer("⚠️ Invalid Solana wallet address. It must be 32–44 characters long and use only valid characters.")

@dp.callback_query_handler(lambda c: c.data == 'wallet')
async def handle_wallet(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
        "💳 Please enter your Solana wallet address.",
        parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == 'invite')
async def handle_invite(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    referral_link = f"https://t.me/{BOT_USERNAME}?start={callback_query.from_user.id}"
    await bot.send_message(callback_query.from_user.id,
        "🚀 Invite your friends to join MarsUnity and receive cosmic karma!\n\n"
        "<b>Join MarsUnity</b> — the meme token with purpose.\n\n"
        f"<b>Your invite link:</b>\n{referral_link}",
        parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == 'about')
async def handle_about(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
        "🌌 <b>About MarsUnity</b>\n\nMarsUnity is a meme token building a brave new world on Solana.\n\n"
        "Explore more: https://marsunity.com",
        parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == 'buy')
async def handle_buy(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
        "💰 <b>How to Buy</b>\n\nYou can buy MarsU tokens on Solana DEXs like Jupiter or through this link:\n"
        "https://dexscreener.com/solana/df9oesxjyjhjwyctwedpm66yojez2yve5qy6vwmfmu42",
        parse_mode="HTML")

if __name__ == '__main__':
    from asyncio import get_event_loop
    loop = get_event_loop()
    loop.run_until_complete(setup_bot_username())
    executor.start_polling(dp, skip_updates=True)
