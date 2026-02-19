import os, time, asyncio, logging
from aiohttp import web
from hydrogram import Client, filters, idle
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URL = os.environ.get("DB_URL")
ADMIN = int(os.environ.get("ADMIN", 0))

# --- DATABASE ---
db_client = AsyncIOMotorClient(DB_URL)
db = db_client["ProRenameBotV2"]
user_data = db["users"]
settings_data = db["settings"]

async def get_bot_settings():
    doc = await settings_data.find_one({"_id": "config"})
    return doc if doc else {"is_public": False}

# --- WEB SERVER ---
async def handle(request): return web.Response(text="Bot is Alive! 🚀")
async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle)
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()

app = Client("pro_rename_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- UTILS ---
def humanbytes(size):
    if not size: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024: return f"{size:.2f} {unit}"
        size /= 1024

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
    settings = await get_bot_settings()
    text = (f"🔥 **Welcome to Pro Rename Bot!**\n\n"
            f"Hello {message.from_user.first_name}, I am a high-speed file renamer.\n\n"
            f"📢 **Current Status:** `{'Public' if settings['is_public'] else 'Private'}`")
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Help", callback_data="help_menu")],
        [InlineKeyboardButton("🖼 Thumbnail", callback_data="thumb_menu"), InlineKeyboardButton("📝 Caption", callback_data="cap_menu")]
    ])
    if message.reply_markup: await message.edit_text(text, reply_markup=buttons)
    else: await message.reply_text(text, reply_markup=buttons)

@app.on_callback_query(filters.regex("help_menu|back_home|thumb_menu|cap_menu|del_thumb_cb|del_cap_cb"))
async def cb_handler(client, cb):
    data = await user_data.find_one({"_id": cb.from_user.id}) or {}
    if cb.data == "help_menu":
        help_t = ("🚀 **Help Menu**\n\nUse `/set_caption {filename}` to set dynamic caption.\nUse `/set_thumb` to save thumbnail.")
        await cb.message.edit(help_t, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))
    elif cb.data == "back_home": await start(client, cb.message)
    elif cb.data == "thumb_menu":
        thumb = data.get("thumb")
        if thumb:
            await cb.message.delete()
            await client.send_photo(cb.message.chat.id, thumb, caption="🖼 **Current Thumbnail**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 Delete", callback_data="del_thumb_cb"), InlineKeyboardButton("⬅️ Back", callback_data="back_home")]]))
        else: await cb.answer("❌ No thumbnail saved!", show_alert=True)
    elif cb.data == "del_thumb_cb":
        await user_data.update_one({"_id": cb.from_user.id}, {"$set": {"thumb": None}})
        await cb.answer("🗑 Deleted!", show_alert=True)
        await start(client, cb.message)

@app.on_message(filters.command("set_thumb") & filters.reply)
async def s_thumb(client, message):
    if not message.reply_to_message.photo: return await message.reply("❌ Reply to a photo!")
    await user_data.update_one({"_id": message.from_user.id}, {"$set": {"thumb": message.reply_to_message.photo.file_id}}, upsert=True)
    await message.reply("✅ **Custom Thumbnail Saved!**")

@app.on_message(filters.command("set_caption"))
async def s_cap(client, message):
    try:
        cap = message.text.split(" ", 1)[1]
        await user_data.update_one({"_id": message.from_user.id}, {"$set": {"caption": cap}}, upsert=True)
        await message.reply(f"✅ **Caption Saved!**")
    except: await message.reply("Usage: `/set_caption File: {filename}`")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_handler(client, message):
    user_id = message.from_user.id
    settings = await get_bot_settings()
    if not settings['is_public'] and user_id != ADMIN: return
    
    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio): return
    
    try: new_name = message.text.split(" ", 1)[1]
    except: return await message.reply("❌ Usage: `/rename filename.mkv`")

    m = await message.reply("📥 **Downloading...**")
    start_time = time.time()
    
    try:
        # --- FIXED DOWNLOAD PATH ---
        raw_path = await client.download_media(reply, file_name=new_name, progress=progress_bar, progress_args=(m, start_time))
        file_path = str(raw_path) # Converting PosixPath to string to fix error
        
        u_data = await user_data.find_one({"_id": user_id}) or {}
        thumb_id = u_data.get("thumb")
        custom_caption = u_data.get("caption")
        caption = custom_caption.replace("{filename}", new_name) if custom_caption else new_name

        thumb_path = None
        if thumb_id:
            raw_thumb = await client.download_media(thumb_id, file_name=f"thumb_{user_id}.jpg")
            thumb_path = str(raw_thumb)

        duration = width = height = 0
        if file_path.lower().endswith((".mp4", ".mkv", ".webm")):
            metadata = extractMetadata(createParser(file_path))
            if metadata:
                if metadata.has("duration"): duration = metadata.get('duration').seconds
                if metadata.has("width"): width = metadata.get('width')
                if metadata.has("height"): height = metadata.get('height')

        await m.edit("📤 **Uploading...**")
        start_u = time.time()

        if reply.video or file_path.lower().endswith((".mp4", ".mkv", ".webm")):
            await client.send_video(message.chat.id, video=file_path, thumb=thumb_path, caption=caption, duration=duration, width=width, height=height, progress=progress_bar, progress_args=(m, start_u))
        else:
            await client.send_document(message.chat.id, file_path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(m, start_u))
        
        await m.delete()
    except Exception as e:
        await m.edit(f"❌ **Error:** `{e}`")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)
        if 'thumb_path' in locals() and thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)

async def main():
    await start_web_server()
    await app.start()
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
