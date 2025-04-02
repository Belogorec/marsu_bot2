import os
import json
import base64
import logging
import datetime
from aiogram import Bot, Dispatcher, executor, types
import gspread
from google.oauth2.service_account import Credentials
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Load config from env
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

welcome_keyboard = InlineKeyboardMarkup(row_width=2).add(
    InlineKeyboardButton("📬 Invite Friends", callback_data="invite"),
    InlineKeyboardButton("📥 Submit Wallet", callback_data="wallet"),
    InlineKeyboardButton("🪐 About MarsUnity", callback_data="about"),
    InlineKeyboardButton("💱 How to Buy", callback_data="buy"),
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

    if not is_registered(user_id):
        users_sheet.append_row([user_id, username, ''])
        log_action(user_id, username, "Registered")

    await message.answer(
        "\U0001F680 Welcome to the *MarsUnity Airdrop*!\n\n"
        "Complete these tasks to join the airdrop:\n\n"
        "1. Follow us on [Twitter](https://x.com/MarsUnity42)\n"
        "2. Join our [Telegram](https://t.me/marsunity42)\n"
        "3. Invite friends (see button below)\n"
        "4. Submit your Solana wallet address (starting with `5...`)\n\n"
        "To participate, you *must*:\n"
        "- Be subscribed to @marsunity42\n"
        "- Provide a valid Solana address\n\n"
        "Use the buttons below to continue:",
        parse_mode='Markdown',
        reply_markup=welcome_keyboard
    )

@dp.message_handler(lambda message: message.chat.type == 'private')
async def handle_wallet_input(message: types.Message):
    user_id = message.from_user.id
    wallet = message.text.strip()

    if wallet.startswith('5') and len(wallet) > 20:
        if update_wallet(user_id, wallet):
            await message.answer("✅ Wallet saved successfully! You're all set for the airdrop.")
        else:
            await message.answer("⛅ Wallet already submitted or registration not started. Type /start to begin.")
    elif wallet.lower() in ['/status', '/help', '/start']:
        pass
    else:
        await message.answer("❌ This doesn't look like a valid Solana wallet. It should start with `5...`.")

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

@dp.message_handler(commands=['help'])
async def show_help(message: types.Message):
    await message.answer(
        "🔮 *What is MarsUnity?*\n"
        "MarsUnity is a meme token with philosophy and irony.\n"
        "We're building a new life on Mars, rewarding those who believe early.\n\n"
        "📈 Buy MarsU: https://dexscreener.com/solana/df9oesxjyjhjwyctwedpm66yojez2yve5qy6vwmfmu42\n"
        "🌐 Website: https://marsunity.com\n\n"
        "Commands:\n/start — restart the bot\n/status — check your status\n/help — info about the project",
        parse_mode='Markdown'
    )

@dp.callback_query_handler(lambda c: c.data == 'invite')
async def handle_invite(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
        "🚀 Invite your friends to join MarsUnity and receive cosmic karma:\n\n"
        "`Join MarsUnity — the meme token with purpose! 🚀 t.me/marsunity42`",
        parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == 'wallet')
async def handle_wallet_info(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
        "📥 Just type your Solana wallet address (starting with `5...`) right here in the chat.")

@dp.callback_query_handler(lambda c: c.data == 'about')
async def handle_about(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
        "🪐 *About MarsUnity:*\n"
        "MarsUnity is a meme token with a mission. Philosophy meets irony on the red planet.\n\n"
        "🌐 Website: https://marsunity.com",
        parse_mode='Markdown')

@dp.callback_query_handler(lambda c: c.data == 'buy')
async def handle_buy(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id,
        "💱 *How to Buy MarsU:*\n"
        "Trade on Dexscreener:\n"
        "https://dexscreener.com/solana/df9oesxjyjhjwyctwedpm66yojez2yve5qy6vwmfmu42\n\n"
        "Make sure you have SOL in your wallet to trade.",
        parse_mode='Markdown')

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
