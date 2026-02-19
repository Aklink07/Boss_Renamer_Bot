import os
import time
import asyncio
import logging
from aiohttp import web
from hydrogram import Client, filters, idle
from motor.motor_asyncio import AsyncIOMotorClient

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
db = db_client["ProRenameBot"]
user_data = db["users"]

async def update_data(user_id, key, value):
    await user_data.update_one({"_id": user_id}, {"$set": {key: value}}, upsert=True)

# --- WEB SERVER (aiohttp) ---
async def handle(request):
    return web.Response(text="Bot is Alive and Pro! 🚀")

async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle)
    runner = web.AppRunner(server)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', 8080).start()
    print("✅ Web Server started on Port 8080")

# --- BOT CLIENT ---
app = Client("rename_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- PROGRESS BAR ---
async def progress_bar(current, total, status_msg, start_time):
    now = time.time()
    if round(now - start_time) % 5 == 0 or current == total:
        percentage = current * 100 / total
        try: await status_msg.edit(f"**Processing:** {round(percentage, 2)}% ⬆️")
        except: pass

# --- HANDLERS ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(f"👋 **Hi {message.from_user.first_name}!**\nI am a Pro Rename Bot (Fixed). Send a file to rename.")

@app.on_message(filters.command("set_thumb") & filters.reply)
async def set_t(client, message):
    if message.from_user.id != ADMIN: return
    if message.reply_to_message.photo:
        await update_data(message.from_user.id, "thumb", message.reply_to_message.photo.file_id)
        await message.reply("✅ Thumbnail Saved!")

@app.on_message(filters.command("rename") & filters.reply)
async def ren(client, message):
    if message.from_user.id != ADMIN: return
    reply = message.reply_to_message
    if not (reply.document or reply.video or reply.audio): return
    
    try: new_name = message.text.split(" ", 1)[1]
    except: return await message.reply("Usage: `/rename filename.mkv`")

    m = await message.reply("⬇️ Downloading...")
    start_t = time.time()
    
    try:
        path = await client.download_media(reply, file_name=new_name, progress=progress_bar, progress_args=(m, start_t))
        
        data = await user_data.find_one({"_id": message.from_user.id}) or {}
        t_id = data.get("thumb")
        t_path = await client.download_media(t_id) if t_id else None

        await m.edit("⬆️ Uploading...")
        start_u = time.time()
        
        await client.send_document(message.chat.id, path, thumb=t_path, caption=new_name, progress=progress_bar, progress_args=(m, start_u))
        
        await m.delete()
        if os.path.exists(path): os.remove(path)
        if t_path and os.path.exists(t_path): os.remove(t_path)
    except Exception as e:
        await m.edit(f"❌ Error: {e}")

# --- MAIN RUNNER ---
async def main():
    await start_web_server()
    await app.start()
    print("✅ Bot is Online with Hydrogram!")
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
