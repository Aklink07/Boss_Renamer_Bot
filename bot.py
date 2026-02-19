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
db = db_client["RenameBotPro_NoThumb"]
user_data = db["users"]
settings_data = db["settings"]

async def is_bot_public():
    doc = await settings_data.find_one({"_id": "config"})
    return doc.get("public", False) if doc else False

# --- WEB SERVER (For UptimeRobot) ---
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
        info = f"\n🚀 Speed: {get_human_size(speed)}/s\n📦 Done: {get_human_size(current)} / {get_human_size(total)}\n⏳ ETA: {round(eta)}s"
        try: await status_msg.edit(f"**⚡ Securely Processing...**\n\n{bar}\n{info}")
        except: pass

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start(client, message):
    is_pub = await is_bot_public()
    text = (f"🛡️ **Advanced Rename Bot v2.0**\n\n"
            f"Hello {message.from_user.first_name}, I am a high-speed secure file renamer.\n\n"
            f"🔹 **Mode:** `{'Public (Open)' if is_pub else 'Private (Admin Only)'}`\n\n"
            "**Commands:**\n"
            "📝 `/set_caption Your Text` - Save Caption\n"
            "❌ `/del_caption` - Remove Caption\n"
            "🔄 Reply to file with `/rename NewName.ext` to begin.")
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Help", callback_data="help_msg")],
        [InlineKeyboardButton("📝 My Caption", callback_data="view_cap")]
    ])
    await message.reply_text(text, reply_markup=buttons)

@app.on_callback_query(filters.regex("help_msg|back|view_cap"))
async def cb_handler(client, cb):
    if cb.data == "help_msg":
        await cb.message.edit("🚀 **How to Rename?**\n\n1. Send any file.\n2. Reply to it with `/rename NewName.mp4`.\n\n"
                              "💡 **Caption Trick:** Use `{filename}` in your caption to automatically insert the new file name.", 
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    elif cb.data == "view_cap":
        data = await user_data.find_one({"_id": cb.from_user.id}) or {}
        cap = data.get("caption", "Default (Filename Only)")
        await cb.message.edit(f"📝 **Current Caption Template:**\n\n`{cap}`", 
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]]))
    elif cb.data == "back":
        await start(client, cb.message)

@app.on_message(filters.command("mode") & filters.user(ADMIN))
async def change_mode(client, message):
    try:
        val = message.text.split(" ", 1)[1].lower()
        new_mode = True if val == "public" else False
        await settings_data.update_one({"_id": "config"}, {"$set": {"public": new_mode}}, upsert=True)
        await message.reply(f"✅ Bot mode updated to **{val.upper()}**")
    except: await message.reply("Usage: `/mode public` or `/mode private`")

@app.on_message(filters.command("set_caption"))
async def s_cap(client, message):
    try:
        cap = message.text.split(" ", 1)[1]
        await user_data.update_one({"_id": message.from_user.id}, {"$set": {"caption": cap}}, upsert=True)
        await message.reply("✅ **Custom Caption Saved!**")
    except: await message.reply("Usage: `/set_caption My Name: {filename}`")

@app.on_message(filters.command("del_caption"))
async def d_cap(client, message):
    await user_data.update_one({"_id": message.from_user.id}, {"$set": {"caption": None}})
    await message.reply("🗑️ **Caption Deleted!**")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_handler(client, message):
    user_id = message.from_user.id
    is_pub = await is_bot_public()
    
    # SECURITY CHECK
    if not is_pub and user_id != ADMIN:
        return await message.reply("🔒 **Private Bot:** Only Admin can use this bot currently.")

    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio):
        return await message.reply("❌ Please reply to a File, Video, or Audio.")
    
    try:
        new_name = message.text.split(" ", 1)[1]
    except IndexError:
        return await message.reply("❌ Provide a name: `/rename My_Movie.mp4`")

    m = await message.reply("📥 **Downloading to Secure Server...**")
    start_time = time.time()
    
    try:
        # Download
        raw_path = await client.download_media(reply, file_name=new_name, progress=progress_bar, progress_args=(m, start_time))
        file_path = str(raw_path) # Critical for PosixPath error
        
        # Caption Logic
        u_data = await user_data.find_one({"_id": user_id}) or {}
        custom_caption = u_data.get("caption")
        caption = custom_caption.replace("{filename}", new_name) if custom_caption else new_name

        await m.edit("📤 **Uploading Securely...**")
        start_u = time.time()

        # Send File
        await client.send_document(
            chat_id=message.chat.id,
            document=file_path,
            caption=caption,
            progress=progress_bar,
            progress_args=(m, start_u)
        )
        
        await m.delete()
    except Exception as e:
        await m.edit(f"❌ **Security Error:** `{e}`")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

# --- STARTUP ---
async def main():
    await start_web_server()
    await app.start()
    print("✅ Secure Rename Bot Online!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
