import os, time, asyncio, logging
from aiohttp import web
from hydrogram import Client, filters, idle
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from motor.motor_asyncio import AsyncIOMotorClient

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URL = os.environ.get("DB_URL")
ADMIN = int(os.environ.get("ADMIN", 0))

# --- DATABASE SETUP ---
db_client = AsyncIOMotorClient(DB_URL)
db = db_client["ProRenameBotV2"]
user_data = db["users"]
settings_data = db["settings"]

async def get_bot_settings():
    doc = await settings_data.find_one({"_id": "config"})
    return doc if doc else {"is_public": False}

async def update_bot_mode(mode: bool):
    await settings_data.update_one({"_id": "config"}, {"$set": {"is_public": mode}}, upsert=True)

# --- WEB SERVER (For Render Uptime) ---
async def handle(request): return web.Response(text="Pro Bot is Flying! ✈️")
async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle)
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()

# --- BOT CLIENT ---
app = Client("pro_rename_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- UTILS ---
def humanbytes(size):
    if not size: return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

async def progress_bar(current, total, status_msg, start_time):
    now = time.time()
    diff = now - start_time
    if round(diff % 5) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        eta = (total - current) / speed if speed > 0 else 0
        p_bar = f"**[{'■' * int(percentage/10)}{'□' * (10 - int(percentage/10))}]** {round(percentage, 2)}%"
        tmp = f"🚀 Speed: {humanbytes(speed)}/s\n📦 Done: {humanbytes(current)} / {humanbytes(total)}\n⏳ ETA: {round(eta)}s"
        try: await status_msg.edit(f"**⚡ Processing Your File...**\n\n{p_bar}\n{tmp}")
        except: pass

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start(client, message):
    text = (f"🔥 **Welcome to Pro Rename Bot!**\n\n"
            f"Hello {message.from_user.first_name}, I am a high-speed file renamer with custom thumbnail and caption support.\n\n"
            f"📢 **Current Status:** `{'Public' if (await get_bot_settings())['is_public'] else 'Private'}`")
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Help & Usage", callback_data="help_menu")],
        [InlineKeyboardButton("🖼 Thumbnail", callback_data="thumb_menu"), InlineKeyboardButton("📝 Caption", callback_data="cap_menu")]
    ])
    await message.reply_text(text, reply_markup=buttons)

@app.on_callback_query(filters.regex("help_menu"))
async def help_cb(client, cb):
    help_text = ("🚀 **Help Menu**\n\n"
                 "1️⃣ **Rename:** Send any file and reply to it with `/rename NewName.ext`.\n"
                 "2️⃣ **Thumbnail:** Send a photo and reply to it with `/set_thumb`.\n"
                 "3️⃣ **Caption:** Use `/set_caption` followed by your text.\n"
                 "4️⃣ **Large Files:** I support files up to 2GB.\n\n"
                 "**Admin Commands:** `/mode public` or `/mode private`")
    await cb.message.edit(help_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))

@app.on_callback_query(filters.regex("back_home"))
async def back_home(client, cb):
    await start(client, cb.message)

@app.on_message(filters.command("mode") & filters.user(ADMIN))
async def toggle_mode(client, message):
    try:
        choice = message.text.split(" ", 1)[1].lower()
        if choice == "public":
            await update_bot_mode(True)
            await message.reply("✅ Bot is now **PUBLIC** (Everyone can use).")
        else:
            await update_bot_mode(False)
            await message.reply("🔒 Bot is now **PRIVATE** (Only Admin can use).")
    except: await message.reply("Usage: `/mode public` or `/mode private`")

@app.on_message(filters.command("set_thumb") & filters.reply)
async def s_thumb(client, message):
    if not message.reply_to_message.photo: return await message.reply("Reply to a photo!")
    await user_data.update_one({"_id": message.from_user.id}, {"$set": {"thumb": message.reply_to_message.photo.file_id}}, upsert=True)
    await message.reply("✅ **Custom Thumbnail Saved!**")

@app.on_message(filters.command("set_caption"))
async def s_cap(client, message):
    try:
        cap = message.text.split(" ", 1)[1]
        await user_data.update_one({"_id": message.from_user.id}, {"$set": {"caption": cap}}, upsert=True)
        await message.reply(f"✅ **Caption Saved:**\n`{cap}`")
    except: await message.reply("Usage: `/set_caption Your Text Here`")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_handler(client, message):
    user_id = message.from_user.id
    settings = await get_bot_settings()
    if not settings['is_public'] and user_id != ADMIN:
        return await message.reply("🔒 **Sorry!** This bot is currently in private mode.")

    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio): return
    
    try: new_name = message.text.split(" ", 1)[1]
    except: return await message.reply("❌ **Error:** Please provide a new name.\nExample: `/rename movie.mkv`")

    m = await message.reply("📥 **Downloading to high-speed server...**")
    start_time = time.time()
    
    try:
        # Step 1: Download
        file_path = await client.download_media(reply, file_name=new_name, progress=progress_bar, progress_args=(m, start_time))
        
        # Step 2: Get User Settings
        u_data = await user_data.find_one({"_id": user_id}) or {}
        thumb_id = u_data.get("thumb")
        caption = u_data.get("caption") or new_name
        
        thumb_path = await client.download_media(thumb_id) if thumb_id else None
        
        await m.edit("📤 **Uploading to Telegram...**")
        start_u = time.time()

        # Step 3: Upload with Large File Handling
        if reply.document:
            await client.send_document(message.chat.id, file_path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(m, start_u))
        elif reply.video:
            await client.send_video(message.chat.id, file_path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(m, start_u))
        elif reply.audio:
            await client.send_audio(message.chat.id, file_path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(m, start_u))
        
        await m.delete()
        if os.path.exists(file_path): os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
        
    except Exception as e:
        await m.edit(f"❌ **Error:** `{e}`")

# --- START BOT ---
async def main():
    await start_web_server()
    await app.start()
    print("🚀 Pro Rename Bot Started Successfully!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
