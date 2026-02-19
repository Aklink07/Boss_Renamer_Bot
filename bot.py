import os
import time
import logging
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters, idle
from motor.motor_asyncio import AsyncIOMotorClient

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
print("--> Checking Environment Variables...")

try:
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    DB_URL = os.environ.get("DB_URL")
    ADMIN = int(os.environ.get("ADMIN", 0))

    if API_ID == 0 or not API_HASH or not BOT_TOKEN or not DB_URL:
        logger.error("❌ CRITICAL ERROR: Variables Missing! Check Render Settings.")
        exit(1)
        
except ValueError:
    logger.error("❌ ERROR: API_ID or ADMIN must be numbers.")
    exit(1)

# --- FLASK KEEP ALIVE (UptimeRobot) ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is Running! 🚀"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# --- DATABASE CONNECTION ---
mongo = AsyncIOMotorClient(DB_URL)
db = mongo["RenameBot"]
thumb_col = db["thumbnails"]

# --- BOT CLIENT ---
app = Client("my_rename_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- FUNCTIONS ---
async def set_thumb(user_id, file_id):
    await thumb_col.update_one({"_id": user_id}, {"$set": {"file_id": file_id}}, upsert=True)

async def get_thumb(user_id):
    doc = await thumb_col.find_one({"_id": user_id})
    return doc["file_id"] if doc else None

async def del_thumb(user_id):
    await thumb_col.delete_one({"_id": user_id})

async def progress(current, total, message, start_time):
    now = time.time()
    diff = now - start_time
    if round(diff % 5.00) == 0 or current == total:
        percentage = current * 100 / total
        try:
            await message.edit_text(f"**Progress:** {round(percentage, 2)}% ⬆️")
        except:
            pass

# --- HANDLERS ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(f"👋 Hello {message.from_user.first_name}! I am Alive.")

@app.on_message(filters.command("set_thumb") & filters.reply)
async def save_thumbnail(client, message):
    if message.from_user.id != ADMIN: return
    if message.reply_to_message.photo:
        await set_thumb(message.from_user.id, message.reply_to_message.photo.file_id)
        await message.reply_text("✅ Thumbnail Saved!")

@app.on_message(filters.command("del_thumb"))
async def delete_thumbnail(client, message):
    if message.from_user.id != ADMIN: return
    await del_thumb(message.from_user.id)
    await message.reply_text("🗑️ Thumbnail Deleted!")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_file(client, message):
    if message.from_user.id != ADMIN:
        return await message.reply("❌ Only Admin can use this.")

    reply = message.reply_to_message
    media = reply.document or reply.video or reply.audio
    if not media: return await message.reply("❌ Reply to a file.")

    try:
        new_name = message.text.split("/rename ", 1)[1]
    except:
        return await message.reply("❌ Usage: `/rename new_name.mkv`")

    status = await message.reply("⬇️ Downloading...")
    
    try:
        path = await client.download_media(reply, file_name=new_name)
        thumb_id = await get_thumb(message.from_user.id)
        thumb_path = await client.download_media(thumb_id) if thumb_id else None
        
        await status.edit("⬆️ Uploading...")
        
        start_time = time.time()
        if reply.document:
            await client.send_document(message.chat.id, path, thumb=thumb_path, caption=new_name, progress=progress, progress_args=(status, start_time))
        elif reply.video:
            await client.send_video(message.chat.id, path, thumb=thumb_path, caption=new_name, progress=progress, progress_args=(status, start_time))
        elif reply.audio:
            await client.send_audio(message.chat.id, path, thumb=thumb_path, caption=new_name, progress=progress, progress_args=(status, start_time))
            
        await status.delete()
        await message.reply("✅ Done!")
        
        if os.path.exists(path): os.remove(path)
        if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
        
    except Exception as e:
        await status.edit(f"❌ Error: {e}")

# --- FIX: MAIN EXECUTION BLOCK ---
async def main():
    # Start Flask in background
    keep_alive()
    
    # Start Bot
    print("✅ Starting Bot...")
    await app.start()
    print("✅ Bot is Online!")
    
    # Keep the bot running
    await idle()
    
    # Stop Bot
    await app.stop()
    print("❌ Bot Stopped.")

if __name__ == "__main__":
    # This loop fixes the 'RuntimeError'
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
