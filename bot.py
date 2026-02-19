import os, time, asyncio, logging
from threading import Thread
from flask import Flask
from pyrogram import Client, filters, idle
from motor.motor_asyncio import AsyncIOMotorClient

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URL = os.environ.get("DB_URL")
ADMIN = int(os.environ.get("ADMIN", 0))

# --- WEB SERVER FOR UPTIME ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Pro Bot is Online! 🚀"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- DATABASE ---
db_client = AsyncIOMotorClient(DB_URL)
db = db_client["ProRenameBot"]
user_data = db["users"]

async def get_data(user_id):
    return await user_data.find_one({"_id": user_id}) or {}

async def update_data(user_id, key, value):
    await user_data.update_one({"_id": user_id}, {"$set": {key: value}}, upsert=True)

# --- BOT CLIENT ---
app = Client("rename_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- PROGRESS BAR ---
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
        progress = f"**[{'■' * int(percentage/10)}{'□' * (10 - int(percentage/10))}]** {round(percentage, 2)}%"
        details = f"\n🚀 Speed: {get_size(speed)}/s\n📦 {get_size(current)} / {get_size(total)}"
        try: await status_msg.edit(f"**Uploading...**\n{progress}{details}")
        except: pass

# --- HANDLERS ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(f"👋 **Hello {message.from_user.first_name}!**\nI am your Pro Rename Bot.\nSend a file and reply with `/rename`.")

@app.on_message(filters.command("set_thumb") & filters.reply)
async def set_t(client, message):
    if message.from_user.id != ADMIN: return
    if message.reply_to_message.photo:
        await update_data(message.from_user.id, "thumb", message.reply_to_message.photo.file_id)
        await message.reply("✅ Thumbnail Saved!")

@app.on_message(filters.command("set_caption"))
async def set_c(client, message):
    if message.from_user.id != ADMIN: return
    try:
        caption = message.text.split(" ", 1)[1]
        await update_data(message.from_user.id, "caption", caption)
        await message.reply(f"✅ Caption Saved!")
    except: await message.reply("Usage: `/set_caption My Text`")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_process(client, message):
    if message.from_user.id != ADMIN: return
    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio): return
    
    try: new_name = message.text.split(" ", 1)[1]
    except: return await message.reply("Usage: `/rename filename.mp4`")

    status = await message.reply("⬇️ Downloading...")
    start_time = time.time()
    
    try:
        path = await client.download_media(reply, file_name=new_name, progress=progress_bar, progress_args=(status, start_time))
        
        data = await get_data(message.from_user.id)
        thumb_id = data.get("thumb")
        caption = data.get("caption") or new_name
        
        thumb_path = await client.download_media(thumb_id) if thumb_id else None
        
        await status.edit("⬆️ Uploading...")
        start_t = time.time()
        
        if reply.document:
            await client.send_document(message.chat.id, path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(status, start_t))
        elif reply.video:
            await client.send_video(message.chat.id, path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(status, start_t))
        elif reply.audio:
            await client.send_audio(message.chat.id, path, thumb=thumb_path, caption=caption, progress=progress_bar, progress_args=(status, start_t))
        
        await status.delete()
        if os.path.exists(path): os.remove(path)
        if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)
    except Exception as e:
        await status.edit(f"❌ Error: {e}")

# --- STARTUP ---
async def main():
    Thread(target=run_web, daemon=True).start()
    await app.start()
    print("✅ Bot is Online with Python 3.10!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
