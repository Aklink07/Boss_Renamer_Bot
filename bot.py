import os
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient

# --- CONFIGURATION (Environment Variables) ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DB_URL = os.environ.get("DB_URL")
ADMIN = int(os.environ.get("ADMIN")) # Tumhari User ID

# --- DATABASE CONNECTION (MongoDB) ---
mongo = AsyncIOMotorClient(DB_URL)
db = mongo["RenameBot"]
thumb_col = db["thumbnails"]

# --- BOT CLIENT ---
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- DATABASE FUNCTIONS ---
async def set_thumb(user_id, file_id):
    await thumb_col.update_one({"_id": user_id}, {"$set": {"file_id": file_id}}, upsert=True)

async def get_thumb(user_id):
    doc = await thumb_col.find_one({"_id": user_id})
    return doc["file_id"] if doc else None

async def del_thumb(user_id):
    await thumb_col.delete_one({"_id": user_id})

# --- PROGRESS BAR FUNCTION ---
async def progress(current, total, message, start_time):
    now = time.time()
    if now - start_time < 5: return # Update every 5 seconds
    try:
        await message.edit_text(f"Uploading... {current * 100 // total}%")
    except: pass

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 **Hello! Main File Rename Bot hoon.**\n\n"
        "1. Koi bhi File/Video bhejo.\n"
        "2. Us file par Reply karke `/rename new_name.ext` likho.\n"
        "3. Thumbnail set karne ke liye photo bhejo aur uspar `/set_thumb` reply karo."
    )

@app.on_message(filters.command("set_thumb") & filters.reply)
async def save_thumb(client, message):
    if message.reply_to_message.photo:
        await set_thumb(message.from_user.id, message.reply_to_message.photo.file_id)
        await message.reply_text("✅ **Thumbnail Saved!** Ab har file me ye lagega.")
    else:
        await message.reply_text("❌ Kisi photo pe reply karke command do.")

@app.on_message(filters.command("del_thumb"))
async def delete_thumbnail(client, message):
    await del_thumb(message.from_user.id)
    await message.reply_text("🗑️ **Thumbnail Deleted!**")

@app.on_message(filters.command("rename") & filters.reply)
async def rename_file(client, message):
    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio):
        return await message.reply_text("❌ Sirf File/Video rename kar sakta hoon.")
    
    # New Name nikalo
    try:
        new_name = message.text.split("/rename ", 1)[1]
    except IndexError:
        return await message.reply_text("❌ Aise likho: `/rename new_filename.mkv`")

    msg = await message.reply_text("⬇️ **Downloading...**")
    
    # File Download
    path = await client.download_media(reply, file_name=new_name)
    
    # Check Custom Thumbnail
    thumb_id = await get_thumb(message.from_user.id)
    thumb_path = None
    if thumb_id:
        thumb_path = await client.download_media(thumb_id)

    await msg.edit_text("⬆️ **Uploading...**")
    
    # File Upload
    try:
        start_time = time.time()
        if reply.document:
            await client.send_document(
                message.chat.id, document=path, thumb=thumb_path, 
                caption=new_name, progress=progress, progress_args=(msg, start_time)
            )
        elif reply.video:
            await client.send_video(
                message.chat.id, video=path, thumb=thumb_path, 
                caption=new_name, progress=progress, progress_args=(msg, start_time)
            )
        elif reply.audio:
            await client.send_audio(
                message.chat.id, audio=path, thumb=thumb_path, 
                caption=new_name, progress=progress, progress_args=(msg, start_time)
            )
        
        await msg.delete()
        await message.reply_text("✅ **Done!**")

    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

    # Cleanup (Delete downloaded files to save space)
    if os.path.exists(path): os.remove(path)
    if thumb_path and os.path.exists(thumb_path): os.remove(thumb_path)

# --- RUN BOT ---
print("Bot Started!")
app.run()
