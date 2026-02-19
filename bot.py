import os, time, asyncio, logging
from threading import Thread
from flask import Flask
from pyrogram import Client, filters, idle
from motor.motor_asyncio import AsyncIOMotorClient

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URL = os.environ.get("DB_URL")
ADMIN = int(os.environ.get("ADMIN", 0))

# --- WEB SERVER FOR UPTIME ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Pro Rename Bot is Running! 🚀"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

Thread(target=run_web, daemon=True).start()

# --- DATABASE SETUP ---
db_client = AsyncIOMotorClient(DB_URL)
db = db_client["ProRenameBot"]
user_data = db["users"]

async def get_data(user_id):
    details = await user_data.find_one({"_id": user_id})
    return details if details else {}

async def update_data(user_id, key, value):
    await user_data.update_one({"_id": user_id}, {"$set": {key: value}}, upsert=True)

# --- BOT CLIENT ---
app = Client("pro_rename_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- PROGRESS BAR UTILS ---
def get_size(bytes):
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
        progress = f"**[{'■' * int(percentage/10)}{'□' * (10 - int(percentage/10))}]** {round(percentage, 2)}%\n"
        details = f"🚀 Speed: {get_size(speed)}/s\n📦 Done: {get_size(current)} / {get_size(total)}\n⏳ ETA: {round(eta)}s"
        try: await status_msg.edit(f"**Processing...**\n\n{progress}{details}")
        except: pass

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(f"👋 **Hi {message.from_user.first_name}!**\n\n"
        "I am a Pro File Rename Bot.\n\n"
        "**Features:**\n"
        "🔹 Reply Photo with `/set_thumb` to save thumbnail.\n"
        "🔹 Use `/set_caption` to save a custom caption.\n"
        "🔹 Reply to a file with `/rename NewName.ext` to rename it.")

@app.on_message(filters.command("set_thumb") & filters.reply)
async def set_thumbnail(client, message):
    if message.from_user.id != ADMIN: return
    if not message.reply_to_message.photo: return await message.reply("Reply to a photo!")
    await update_data(message.from_user.id, "thumb", message.reply_to_message.photo.file_id)
    await message.reply("✅ **Thumbnail Saved!**")

@app.on_message(filters.command("del_thumb"))
async def delete_thumbnail(client, message):
    if message.from_user.id != ADMIN: return
    await update_data(message.from_user.id, "thumb", None)
    await message.reply("🗑️ **Thumbnail Deleted!**")

@app.on_message(filters.command("set_caption"))
async def set_cap(client, message):
    if message.from_user.id != ADMIN: return
    try:
        caption = message.text.split(" ", 1)[1]
        await update_data(message.from_user.id, "caption", caption)
        await message.reply(f"✅ **Custom Caption Set:**\n`{caption}`")
    except: await message.reply("Usage: `/set_caption My Custom Caption`")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_process(client, message):
    if message.from_user.id != ADMIN: return
    
    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio): 
        return await message.reply("❌ Reply to a document, video, or audio file.")
    
    try: new_name = message.text.split(" ", 1)[1]
    except: return await message.reply("Usage: `/rename New_Name.ext`")

    m = await message.reply("⬇️ **Downloading...**")
    start_time = time.time()
    
    try:
        # Download file
        file_path = await client.download_media(reply, file_name=new_name, progress=progress_bar, progress_args=(m, start_time))
        
        # Get Database Settings
        data = await get_data(message.from_user.id)
        thumb_id = data.get("thumb")
        custom_caption = data.get("caption")
        
        # Download thumbnail if exists
        thumb_path = await client.download_media(thumb_id) if thumb_id else None
        caption = custom_caption if custom_caption else new_name

        await m.edit("⬆️ **Uploading...**")
        start_time = time.time()

        # Send file back
        if reply.document:
            await client.send_document(message.chat.id, file_path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(m, start_time))
        elif reply.video:
            await client.send_video(message.chat.id, file_path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(m, start_time))
        elif reply.audio:
            await client.send_audio(message.chat.id, file_path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(m, start_time))

        await m.delete()
        if os.path.exists(file_path): os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
        
    except Exception as e:
        await m.edit(f"❌ **Error:** `{e}`")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("🚀 Bot Starting...")
    app.run()
