import os, time, asyncio, logging
from aiohttp import web
from hydrogram import Client, filters, idle
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URL = os.environ.get("DB_URL")
ADMIN = int(os.environ.get("ADMIN", 0))

# --- DATABASE SETUP ---
db_client = AsyncIOMotorClient(DB_URL)
db = db_client["SecureRenamePro_V3"]
user_data = db["users"]
settings_data = db["settings"]

async def is_bot_public():
    doc = await settings_data.find_one({"_id": "config"})
    return doc.get("public", False) if doc else False

# --- WEB SERVER (For Render Uptime) ---
async def handle(request): return web.Response(text="Bot is Secure & Running! 🛡️")
async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle)
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()

# --- BOT CLIENT ---
app = Client("rename_bot_pro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- UTILS (Size & Progress) ---
def get_human_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024: return f"{bytes:.2f} {unit}"
        bytes /= 1024

async def progress_bar(current, total, status_msg, start_time):
    now = time.time()
    diff = now - start_time
    if round(diff % 5) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0
        bar = f"**[{'■' * int(percentage/10)}{'□' * (10 - int(percentage/10))}]** {round(percentage, 2)}%"
        info = (f"\n\n🚀 **Speed:** {get_human_size(speed)}/s"
                f"\n📦 **Done:** {get_human_size(current)} of {get_human_size(total)}"
                f"\n⏳ **ETA:** {round(eta)} Seconds")
        try: await status_msg.edit(f"✨ **Uploading with High Speed...**\n\n{bar}{info}")
        except: pass

# --- UI MESSAGES ---

START_TEXT = (
    "✨ **Welcome to Pro Rename Bot v3.0** ✨\n\n"
    "Hello **{name}**, I am a premium, high-speed file renamer bot designed for speed and security.\n\n"
    "🛡️ **Current Security:** `{mode}`\n"
    "⚡ **Server Status:** `Online & High Speed`\n\n"
    "I can rename files up to **2GB** instantly with custom caption support!"
)

HELP_TEXT = (
    "🚀 **User Guide & Help Menu**\n\n"
    "**1. How to Rename a File?**\n"
    "👉 Send any File, Video, or Audio to the bot.\n"
    "👉 **Reply** to that file with the command: `/rename New_Name.ext` (Example: `/rename movie.mp4`)\n\n"
    "**2. How to Set a Custom Caption?**\n"
    "👉 Use command: `/set_caption My Cool File: {filename}`\n"
    "👉 The `{filename}` tag will automatically replace with your new file name.\n"
    "👉 Use `/del_caption` to remove it.\n\n"
    "**3. Bot Specifications:**\n"
    "✅ **Max File Size:** 2GB (Telegram Limit)\n"
    "✅ **Encryption:** Secure Processing\n"
    "✅ **Database:** MongoDB Cloud\n\n"
    "**4. Admin Controls:**\n"
    "👉 `/mode public` - Allow everyone to use.\n"
    "👉 `/mode private` - Restrict to Admin only."
)

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start(client, message):
    is_pub = await is_bot_public()
    mode_text = "🔓 Public (All Users)" if is_pub else "🔒 Private (Admin Only)"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Help & Usage", callback_data="help_msg"), InlineKeyboardButton("📝 My Caption", callback_data="view_cap")],
        [InlineKeyboardButton("💎 About Bot", callback_data="about_msg")]
    ])
    
    await message.reply_text(
        START_TEXT.format(name=message.from_user.first_name, mode=mode_text),
        reply_markup=buttons
    )

@app.on_callback_query(filters.regex("help_msg|back|view_cap|about_msg"))
async def cb_handler(client, cb):
    if cb.data == "help_msg":
        await cb.message.edit(HELP_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Home", callback_data="back")]]))
    elif cb.data == "about_msg":
        about = ("💎 **About Pro Rename Bot**\n\n"
                 "👤 **Developer:** Admin\n"
                 "🚀 **Platform:** Hydrogram + Render\n"
                 "📦 **Framework:** Python v3.10+\n"
                 "✨ **Feature:** Dynamic Caption & High Speed Upload")
        await cb.message.edit(about, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Home", callback_data="back")]]))
    elif cb.data == "view_cap":
        data = await user_data.find_one({"_id": cb.from_user.id}) or {}
        cap = data.get("caption", "Default (No custom caption set)")
        await cb.message.edit(f"📝 **Your Caption Template:**\n\n`{cap}`", 
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Home", callback_data="back")]]))
    elif cb.data == "back":
        await start(client, cb.message)

@app.on_message(filters.command("mode") & filters.user(ADMIN))
async def change_mode(client, message):
    try:
        val = message.text.split(" ", 1)[1].lower()
        new_mode = True if val == "public" else False
        await settings_data.update_one({"_id": "config"}, {"$set": {"public": new_mode}}, upsert=True)
        await message.reply(f"✅ Bot mode updated to **{val.upper()}** successfully.")
    except: await message.reply("Usage: `/mode public` or `/mode private`")

@app.on_message(filters.command("set_caption"))
async def s_cap(client, message):
    try:
        cap = message.text.split(" ", 1)[1]
        await user_data.update_one({"_id": message.from_user.id}, {"$set": {"caption": cap}}, upsert=True)
        await message.reply("✅ **Custom Caption Template Saved!**")
    except: await message.reply("Usage: `/set_caption File Name: {filename}`")

@app.on_message(filters.command("del_caption"))
async def d_cap(client, message):
    await user_data.update_one({"_id": message.from_user.id}, {"$set": {"caption": None}})
    await message.reply("🗑️ **Caption Template Deleted!**")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_handler(client, message):
    user_id = message.from_user.id
    is_pub = await is_bot_public()
    
    if not is_pub and user_id != ADMIN:
        return await message.reply("🔒 **Private Bot:** You are not authorized to use this bot.")

    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio):
        return await message.reply("❌ **Error:** Please reply to a valid File or Video.")
    
    try:
        new_name = message.text.split(" ", 1)[1]
    except IndexError:
        return await message.reply("❌ **Error:** Usage: `/rename New_Name.ext`")

    status = await message.reply("📥 **Downloading from Telegram...**")
    start_time = time.time()
    
    try:
        # Download (Converted to string to prevent PosixPath errors)
        raw_path = await client.download_media(reply, file_name=new_name, progress=progress_bar, progress_args=(status, start_time))
        file_path = str(raw_path)
        
        # Caption Processing
        u_data = await user_data.find_one({"_id": user_id}) or {}
        custom_caption = u_data.get("caption")
        caption = custom_caption.replace("{filename}", new_name) if custom_caption else f"**{new_name}**"

        await status.edit("📤 **Uploading to High-Speed Server...**")
        start_u = time.time()

        # Send File
        await client.send_document(
            chat_id=message.chat.id,
            document=file_path,
            caption=caption,
            progress=progress_bar,
            progress_args=(status, start_u)
        )
        
        await status.delete()
    except Exception as e:
        await status.edit(f"❌ **Error:** `{e}`")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

# --- STARTUP ---
async def main():
    await start_web_server()
    await app.start()
    print("✅ Pro Rename Bot is Live!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
