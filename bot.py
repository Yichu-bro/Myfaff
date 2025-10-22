# bot.py

import logging
import datetime
import requests
import json
import asyncio
import nest_asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# This is necessary for running asyncio within another event loop,
# which can happen in some deployment environments.
nest_asyncio.apply()

# ========= CONFIGURATION =========
# --- IMPORTANT FOR DEPLOYMENT ---
# The bot token is loaded from an "Environment Variable" on the hosting platform.
# This is a secure way to store your token without writing it directly in the code.
# On Render, you will set a variable with the Key `BOT_TOKEN` and your actual token as the Value.
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_URL_TEMPLATE = "https://295.vercel.app/like?uid={uid}&server_name={region}" # Your like API

# You can manage these as environment variables too for more flexibility,
# but for simplicity, we will keep them here.
ADMIN_IDS = [6941014837] # Your Telegram User ID
ALLOWED_GROUPS = [1003161051720] # Your Group ID
vip_users = [6941014837] # VIP User IDs
DEFAULT_DAILY_LIMIT = 30 # Default like limit for groups

# ========= STATE VARIABLES (In-memory storage) =========
allowed_groups = set(ALLOWED_GROUPS)
group_usage = {}
group_limits = {}
last_reset_date = {}
user_data = {}
promotion_message = ""
command_enabled = True

# ========= LOGGING SETUP =========
# This configures logging to show informational messages.
# These logs are crucial for debugging on the server.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========= WEB SERVER FOR HOSTING (Keep-Alive Service) =========
# Free hosting services often put applications to "sleep" if they don't receive web traffic.
# This simple web server responds to pings to keep the bot running 24/7.
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is running.")

def run_web_server(port):
    httpd = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    logger.info(f"Starting web server on port {port} to keep bot alive.")
    httpd.serve_forever()

# ========= HELPER FUNCTIONS =========
async def get_user_name(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        user = await context.bot.get_chat(user_id)
        return user.full_name or f"User {user_id}"
    except Exception as e:
        logger.warning(f"Could not get user name for {user_id}: {e}")
        return f"User {user_id}"

def is_group(update: Update):
    return update.message and update.message.chat.type in ["group", "supergroup"]

def get_today():
    return datetime.date.today().strftime("%Y-%m-%d")

def reset_if_needed(group_id: int):
    today = datetime.date.today()
    if last_reset_date.get(group_id) != today:
        group_usage[group_id] = 0
        last_reset_date[group_id] = today

def get_limit(group_id: int):
    return group_limits.get(group_id, DEFAULT_DAILY_LIMIT)

# This decorator checks if commands are globally enabled.
# It also safely handles non-text messages to prevent crashes.
def check_command_enabled(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Ignore updates that are not messages with text (e.g., a user joining)
        if not update.message or not update.message.text:
            return

        if not command_enabled and update.message.text != "/on":
            await update.message.reply_text("🚫 Commands are currently disabled.")
            return
        return await func(update, context)
    return wrapper

# ========= CORE COMMANDS =========
@check_command_enabled
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Use /like <region> <uid> to get Free Fire likes.")

@check_command_enabled
async def bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot code by @Ummedjangir0008 🗿")

@check_command_enabled
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📘 **HELP MENU**

🔹 **Core Commands:**
`/like <region> <uid>` - Send likes (e.g., `/like ind 12345678`)
`/check` - Check your daily usage status.
`/groupstatus` - See the group's daily usage.
`/remain` - See how many users have used the bot today.

🔹 **VIP Management:** (Admin/VIP only)
`/setvip <user_id>` - Add a VIP user.
`/removevip <user_id>` - Remove a VIP.
`/viplist` - Show all VIP users.
`/setpromotion <text>` - Set a promotional message.

🔹 **User & System:**
`/userinfo <user_id>` - Get user details. (Admin only)
`/feedback <message>` - Send feedback to the owner.
`/status` - Check the bot's overall status.

👑 **Owner:** @Ummedjangir0008
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ========= ADMIN MENU COMMAND =========
@check_command_enabled
async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized")
        return
        
    admin_text = """
🔐 **ADMIN MENU**

🔹 **Admin Tools:**
`/allow <group_id>` - Allow a group to use the bot.
`/remove <group_id>` - Remove a group.
`/setremain <number>` - Set the daily like limit for this group.
`/groupreset` - Manually reset usage for all groups.
`/broadcast <message>` - Send a message to all users and groups.
`/send <message>` - Send a message to VIPs & groups.
`/setadmin <user_id>` - Add a new admin.
`/removeadmin <user_id>` - Remove an admin.
`/adminlist` - Show all admins.
`/on` / `/off` - Enable or disable all commands.
"""
    await update.message.reply_text(admin_text, parse_mode='Markdown')

# ========= LIKE COMMAND (The Main Feature) =========
@check_command_enabled
async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        await update.message.reply_text("This command only works in groups.")
        return

    group_id = update.effective_chat.id
    if group_id not in allowed_groups:
        return # Bot will not respond in non-allowed groups

    reset_if_needed(group_id)
    used = group_usage.get(group_id, 0)
    limit = get_limit(group_id)

    if used >= limit:
        await update.message.reply_text("❌ Group daily like limit reached!")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ Usage: `/like <region> <uid>`\nExample: `/like ind 1234567890`")
        return

    processing_msg = await update.message.reply_text("⏳ Processing your request...")

    region, uid = args
    user_id = update.effective_user.id
    today = get_today()
    is_vip = user_id in vip_users

    if not is_vip:
        user_info = user_data.get(user_id, {})
        if user_info.get("date") == today and user_info.get("count", 0) >= 1:
            await processing_msg.edit_text("⛔ You have already used your free like for today.")
            return
        user_data[user_id] = {"date": today, "count": user_info.get("count", 0)}

    try:
        response = requests.get(API_URL_TEMPLATE.format(uid=uid, region=region), timeout=10)
        response.raise_for_status() # Raise an error for bad responses (4xx or 5xx)
        data = response.json()
        logger.info(f"API response for UID {uid}: {data}")
    except requests.exceptions.RequestException as e:
        logger.error(f"API request error: {e}")
        await processing_msg.edit_text("🚨 API Error! The like server might be down. Please try again later.")
        return
    except json.JSONDecodeError:
        logger.error(f"API JSON decode error. Response: {response.text}")
        await processing_msg.edit_text("🚨 API Error! Received an invalid response from the server.")
        return

    if data.get("LikesGivenByAPI") == 0:
        await processing_msg.edit_text("⚠️ This UID has already reached the maximum likes for today from the server.")
        return

    required_keys = ["PlayerNickname", "UID", "LikesbeforeCommand", "LikesafterCommand", "LikesGivenByAPI"]
    if not all(key in data for key in required_keys):
        await processing_msg.edit_text("⚠️ Invalid UID or the region might be wrong. Please check and try again.")
        logger.warning(f"Incomplete API response for UID {uid}: {data}")
        return

    if not is_vip:
        user_data[user_id]["count"] += 1
    group_usage[group_id] = group_usage.get(group_id, 0) + 1

    text = (
        f"✅ **Like Sent Successfully!**\n\n"
        f"👤 **Name:** `{data['PlayerNickname']}`\n"
        f"🆔 **UID:** `{data['UID']}`\n"
        f"📊 **Level:** {data.get('Level', 'N/A')}\n"
        f"🌍 **Region:** {data.get('Region', region.upper())}\n"
        f"👍 **Before:** {data['LikesbeforeCommand']}\n"
        f"📈 **After:** {data['LikesafterCommand']}\n"
        f"🎉 **Likes Given:** **{data['LikesGivenByAPI']}**"
    )
    if promotion_message:
        text += f"\n\n📢 {promotion_message}"

    try:
        await processing_msg.edit_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Failed to send final message: {e}")
        # Fallback to plain text if Markdown fails
        await processing_msg.edit_text(text.replace('`', '').replace('*', ''))
        
# ... [ALL OTHER COMMAND HANDLERS GO HERE] ...
# For brevity, other functions are omitted, but you should have them in your file.
# The structure is the same. Just ensure they are decorated with @check_command_enabled

# ========= GROUP AND USER STATUS COMMANDS =========
@check_command_enabled
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = get_today()
    user_info = user_data.get(user_id, {})
    user_date = user_info.get("date")
    count = user_info.get("count", 0)

    status = "UNLIMITED (VIP)" if user_id in vip_users else (
        f"{count}/1 ✅ Used" if user_date == today else "0/1 ❌ Not Used"
    )
    await update.message.reply_text(f"👤 Dear {update.effective_user.first_name},\nYour daily like status: **{status}**", parse_mode='Markdown')

@check_command_enabled
async def groupstatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return
    group_id = update.effective_chat.id
    count = group_usage.get(group_id, 0)
    await update.message.reply_text(f"📊 **Group Usage Status**\n\nLikes used today: **{count}/{get_limit(group_id)}**", parse_mode='Markdown')

# ... Add all your other admin functions like allow, remove, setvip, etc. here ...

@check_command_enabled
async def off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ You are not authorized.")
        return
    global command_enabled
    command_enabled = False
    await update.message.reply_text("⛔ All commands (except /on) have been disabled.")

@check_command_enabled
async def on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This command should work even when commands are disabled
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ You are not authorized.")
        return
    global command_enabled
    command_enabled = True
    await update.message.reply_text("✅ Commands are now enabled.")

# ========= AUTO RESET BACKGROUND TASK =========
async def reset_group_usage_task():
    while True:
        now = datetime.datetime.now()
        # Reset at 00:00 UTC
        reset_time = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (reset_time - now).total_seconds()
        logger.info(f"Group usage will reset in {wait_seconds / 3600:.2f} hours.")
        await asyncio.sleep(wait_seconds)
        group_usage.clear()
        logger.info("✅ Daily group like limits have been reset.")

# ========= MAIN FUNCTION TO START THE BOT =========
def main() -> None:
    """Start the bot."""
    if not BOT_TOKEN:
        logger.critical("FATAL ERROR: BOT_TOKEN environment variable not found.")
        logger.critical("Please set it on your hosting platform and restart.")
        return

    # Start the web server in a separate thread
    # Render provides the PORT env var. Default to 8080 for local testing.
    port = int(os.environ.get("PORT", 8080))
    web_thread = threading.Thread(target=run_web_server, args=(port,))
    web_thread.daemon = True
    web_thread.start()
    
    # Create the Application and pass it your bot's token.
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add all command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("bot", bot))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("open", open_command))
    application.add_handler(CommandHandler("like", like))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("groupstatus", groupstatus))
    # ... Add all other handlers here ...
    application.add_handler(CommandHandler("off", off))
    # 'on' handler is special; it doesn't use the decorator so it can run when commands are off
    application.add_handler(CommandHandler("on", on))


    # Start the background task for daily resets
    loop = asyncio.get_event_loop()
    loop.create_task(reset_group_usage_task())

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot is starting polling...")
    application.run_polling()


if __name__ == "__main__":
    main()```