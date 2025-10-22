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
    filters,
)

nest_asyncio.apply()

# ========= CONFIG =========
# Securely get the bot token from an environment variable
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_URL_TEMPLATE = "https://295.vercel.app/like?uid={uid}&server_name={region}"#your like api 

# It's better to manage these IDs as environment variables as well for security and flexibility
# For simplicity, we will leave them here, but consider moving them.
ADMIN_IDS = [6941014837] #your telegram id
ALLOWED_GROUPS = [1003161051720] #group id
vip_users = [6941014837] #vip id
DEFAULT_DAILY_LIMIT = 30 #limt your group 

# ========= STATE =========
allowed_groups = set(ALLOWED_GROUPS)
group_usage = {}
group_limits = {}
last_reset_date = {}
user_data = {}
promotion_message = ""
command_enabled = True

# ========= LOGGING =========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========= WEB SERVER FOR HOSTING (Keep-Alive) =========
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<html><head><title>Bot Status</title></head>")
        self.wfile.write(b"<body><p>The Telegram bot is running.</p></body></html>")

def run_web_server(port):
    httpd = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"Starting web server on port {port}...")
    httpd.serve_forever()

# ========= HELPERS =========
async def get_user_name(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    try:
        user = await context.bot.get_chat(user_id)
        return user.full_name or f"User {user_id}"
    except:
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

def check_command_enabled(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text("👋 Welcome! Use /like ind <uid> to get Free Fire likes.")

@check_command_enabled
async def bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("bot code by @Ummedjangir0008 🗿 aka @Ummedjangir0008")

@check_command_enabled
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📘 HELP MENU

🔹 Core Commands:
/like <region> <uid> - Send likes
/check - Your usage today
/groupstatus - Group usage stats
/remain - Today's user count

🔹 VIP Management:
/setvip <user_id> - Add VIP
/removevip <user_id> - Remove VIP
/viplist - Show VIP users
/setpromotion <text> - Set promo msg

🔹 User Management:
/userinfo <user_id> - Get user details
/stats - Usage statistics
/feedback <msg> - Send feedback

🔹 System:
/status - Bot status
/on - Enable commands
/off - Disable commands

👑 Owner: @Ummedjangir0008
"""
    await update.message.reply_text(help_text)

# ========= ADMIN MENU COMMAND =========
@check_command_enabled
async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized")
        return
        
    admin_text = """
🔐 ADMIN MENU

🔹 Admin Tools:
/allow <group_id> - Allow group
/remove <group_id> - Remove group
/setremain <number> - Set group limit
/groupreset - Reset group usage
/broadcast <msg> - Global broadcast
/send <msg> - Send to VIPs & groups
/setadmin [user_id] or reply to user
/removeadmin [user_id] or reply to user
/adminlist - Show admins with names
"""
    await update.message.reply_text(admin_text)

# ========= BROADCAST COMMANDS =========
@check_command_enabled
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Usage: /broadcast <message>")
        return

    text = " ".join(context.args)
    sent = 0
    failed = 0
    msg = await update.message.reply_text("📢 Broadcasting started...")

    # Send to all users
    for user_id in set(user_data.keys()):
        try:
            await context.bot.send_message(user_id, text)
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.1)

    # Send to all groups
    for group_id in allowed_groups:
        try:
            await context.bot.send_message(group_id, text)
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.1)

    await msg.edit_text(f"📢 Broadcast Complete!\n\n✅ Sent: {sent}\n❌ Failed: {failed}")

@check_command_enabled
async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in vip_users:
        await update.message.reply_text("⛔ Unauthorized")
        return

    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("⚠️ Please provide a message to send.")
        return

    success_users = []
    success_groups = []
    failed_users = []
    failed_groups = []

    # Send to VIP users
    for user_id in set(vip_users):
        try:
            user = await context.bot.get_chat(user_id)
            username = f"@{user.username}" if user.username else user.full_name
            await context.bot.send_message(user_id, text)
            success_users.append(f"{username} (ID: {user_id})")
        except Exception as e:
            failed_users.append(f"User {user_id}")
            logger.error(f"Error sending to VIP user {user_id}: {e}")

    # Send to allowed groups
    for group_id in set(allowed_groups):
        try:
            chat = await context.bot.get_chat(group_id)
            group_name = chat.title or f"Group {group_id}"
            await context.bot.send_message(group_id, text)
            success_groups.append(f"{group_name} (ID: {group_id})")
        except Exception as e:
            failed_groups.append(f"Group {group_id}")
            logger.error(f"Error sending to group {group_id}: {e}")

    # Prepare response
    response = "📢 Message Delivery Report\n\n"
    if success_users:
        response += f"✅ Sent to {len(success_users)} users:\n" + "\n".join(success_users) + "\n\n"
    if success_groups:
        response += f"✅ Sent to {len(success_groups)} groups:\n" + "\n".join(success_groups) + "\n\n"
    if failed_users:
        response += f"❌ Failed to send to {len(failed_users)} users:\n" + "\n".join(failed_users) + "\n\n"
    if failed_groups:
        response += f"❌ Failed to send to {len(failed_groups)} groups:\n" + "\n".join(failed_groups)

    await update.message.reply_text(response[:4000])  # Telegram message length limit

# ... [The rest of your bot's command handlers go here, no changes needed] ...
# (like, check, groupstatus, admin commands, etc. - just copy-paste them)
# For brevity, I am omitting the identical functions. Paste your functions from `help_command` to `on` here.

# ========= AUTO RESET TASK =========
async def reset_group_usage_task():
    while True:
        now = datetime.datetime.now()
        # It's better to use UTC time on servers
        reset_time = now.replace(hour=4, minute=30, second=0, microsecond=0)
        if now >= reset_time:
            reset_time += datetime.timedelta(days=1)
        wait_seconds = (reset_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        group_usage.clear()
        print("✅ Group like limits reset at 4:30 AM.")

# ========= MAIN =========
def setup_bot():
    if not BOT_TOKEN:
        raise ValueError("No BOT_TOKEN found. Please set the environment variable.")
        
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add all your command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bot", bot))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("open", open_command))
    app.add_handler(CommandHandler("like", like))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("setpromotion", setpromotion))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("send", send))
    app.add_handler(CommandHandler("groupstatus", groupstatus))
    app.add_handler(CommandHandler("remain", remain))
    app.add_handler(CommandHandler("userinfo", userinfo))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("allow", allow))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("groupreset", groupreset))
    app.add_handler(CommandHandler("setremain", setremain))
    app.add_handler(CommandHandler("autogroupreset", autogroupreset))
    app.add_handler(CommandHandler("setvip", setvip))
    app.add_handler(CommandHandler("removevip", removevip))
    app.add_handler(CommandHandler("viplist", viplist))
    app.add_handler(CommandHandler("setadmin", setadmin))
    app.add_handler(CommandHandler("removeadmin", removeadmin))
    app.add_handler(CommandHandler("adminlist", adminlist))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("restore", restore))
    app.add_handler(CommandHandler("maintenance", maintenance))
    app.add_handler(CommandHandler("feedback", feedback))
    app.add_handler(CommandHandler("off", off))
    app.add_handler(CommandHandler("on", on))

    return app

if __name__ == "__main__":
    # Render provides a PORT environment variable.
    web_server_port = int(os.environ.get("PORT", 8080))

    # Start the web server in a separate thread
    web_server_thread = threading.Thread(target=run_web_server, args=(web_server_port,))
    web_server_thread.daemon = True
    web_server_thread.start()

    # Set up and run the bot
    application = setup_bot()
    loop = asyncio.get_event_loop()
    if not loop.is_running():
        loop.create_task(reset_group_usage_task())
        loop.run_until_complete(application.run_polling())
    else:
        # If a loop is already running (like in some environments), just run the tasks
        asyncio.ensure_future(reset_group_usage_task())
        asyncio.ensure_future(application.run_polling())
