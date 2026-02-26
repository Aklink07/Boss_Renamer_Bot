import os, time, asyncio, logging
from aiohttp import web
from hydrogram import Client, filters, idle
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URL = os.environ.get("DB_URL")
ADMIN = int(os.environ.get("ADMIN", 0))
DEVELOPER_USR = os.environ.get("DEVELOPER_USR", "TechnicalAklink") 

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

app = Client("rename_bot_pro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- UTILS ---
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

# --- UI MESSAGES (BEAUTIFIED) ---

START_TEXT = (
    "✨ **Welcome to Boss_Pro Rename Bot v3.1** ✨\n\n"
    "Hello **{name}**, I am a premium, high-speed file renamer bot designed for speed and security.\n\n"
    "🛡️ **Current Security:** `{mode}`\n"
    "⚡ **Server Status:** `Online & High Speed`\n\n"
    "I can rename files up to **2GB** instantly with custom caption support!"
)

DETAILED_HELP = (
    "🚀 **USER GUIDE & HELP MENU**\n"
    "━━━━━━━━━━━━━━━━━━\n\n"
    "**1️⃣ HOW TO RENAME?**\n"
    "• Send any File, Video, or Audio to the bot.\n"
    "• **Reply** to that file with the command:\n"
    "   `/rename New_File_Name.ext` \n"
    "• *Example:* `/rename movie.mp4`\n\n"
    "**2️⃣ CUSTOM CAPTION**\n"
    "• You can set a professional caption template:\n"
    "   `/set_caption 📂 File: {filename} \n🚀 Join: @Channel` \n"
    "• *Note:* `{filename}` will automatically be replaced with your new file name.\n"
    "• Use `/del_caption` to reset it.\n\n"
    "**3️⃣ BOT SPECIFICATIONS**\n"
    "✅ **Max Size:** 2GB (Telegram Limit)\n"
    "✅ **Speed:** Ultra-Fast Cloud Server\n"
    "✅ **Safety:** Fully Encrypted Processing\n"
    "✅ **Database:** MongoDB Cloud Secured\n\n"
    "**4️⃣ ADMIN ONLY COMMANDS**\n"
    "• `/mode public` - Everyone can use the bot.\n"
    "• `/mode private` - Only Admin can use the bot.\n"
    "━━━━━━━━━━━━━━━━━━"
)

# --- HOME FUNCTION ---
async def send_start_msg(message, is_callback=False):
    is_pub = await is_bot_public()
    mode_text = "🔓 Public" if is_pub else "🔒 Private"
    name = message.from_user.first_name if not is_callback else message.chat.first_name
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Help & Usage", callback_data="help_msg"), InlineKeyboardButton("📝 My Caption", callback_data="view_cap")],
        [InlineKeyboardButton("💎 About Bot", callback_data="about_msg")]
    ])
    text = START_TEXT.format(name=name, mode=mode_text)
    if is_callback: await message.edit_text(text, reply_markup=buttons)
    else: await message.reply_text(text, reply_markup=buttons)

# --- CALLBACK HANDLER ---
@app.on_callback_query(filters.regex("help_msg|back|view_cap|about_msg"))
async def cb_handler(client, cb):
    if cb.data == "help_msg":
        await cb.message.edit(DETAILED_HELP, 
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Home", callback_data="back")]]))
    elif cb.data == "about_msg":
        about = (f"💎 **About Pro Rename Bot**\n\n"
                 f"👤 **Developer:** [{DEVELOPER_USR}](https://t.me/{DEVELOPER_USR})\n"
                 f"🚀 **Platform:** Hydrogram + Render\n"
                 f"📦 **Framework:** Python v3.10+\n"
                 f"✨ **Feature:** Dynamic Caption & High Speed")
        await cb.message.edit(about, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Home", callback_data="back")]]), disable_web_page_preview=True)
    elif cb.data == "view_cap":
        data = await user_data.find_one({"_id": cb.from_user.id}) or {}
        cap = data.get("caption", "Default (No custom caption set)")
        await cb.message.edit(f"📝 **Your Caption Template:**\n\n`{cap}`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Home", callback_data="back")]]))
    elif cb.data == "back":
        await send_start_msg(cb.message, is_callback=True)

# --- COMMANDS ---
@app.on_message(filters.command("start"))
async def start_cmd(client, message): await send_start_msg(message)

@app.on_message(filters.command("mode") & filters.user(ADMIN))
async def change_mode(client, message):
    try:
        val = message.text.split(" ", 1)[1].lower()
        await settings_data.update_one({"_id": "config"}, {"$set": {"public": (val == "public")}}, upsert=True)
        await message.reply(f"✅ Mode updated to {val.upper()}")
    except: await message.reply("Usage: `/mode public` or `/mode private`")

@app.on_message(filters.command("set_caption"))
async def s_cap(client, message):
    try:
        cap = message.text.split(" ", 1)[1]
        await user_data.update_one({"_id": message.from_user.id}, {"$set": {"caption": cap}}, upsert=True)
        await message.reply("✅ Caption Saved!")
    except: await message.reply("Usage: `/set_caption {filename}`")

@app.on_message(filters.command("del_caption"))
async def d_cap(client, message):
    await user_data.update_one({"_id": message.from_user.id}, {"$set": {"caption": None}})
    await message.reply("🗑️ Caption Deleted!")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_handler(client, message):
    if not await is_bot_public() and message.from_user.id != ADMIN:
        return await message.reply("🔒 Private Bot.")
    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio): return
    try:
        new_name = message.text.split(" ", 1)[1]
        status = await message.reply("📥 Downloading...")
        start_t = time.time()
        path = str(await client.download_media(reply, file_name=new_name, progress=progress_bar, progress_args=(status, start_t)))
        u_data = await user_data.find_one({"_id": message.from_user.id}) or {}
        caption = u_data.get("caption", "{filename}").replace("{filename}", new_name)
        await status.edit("📤 Uploading...")
        await client.send_document(message.chat.id, path, caption=caption, progress=progress_bar, progress_args=(status, time.time()))
        await status.delete()
        os.remove(path)
    except Exception as e: await message.reply(f"❌ Error: {e}")

# --- START ---
async def main():
    await start_web_server()
    await app.start()
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
