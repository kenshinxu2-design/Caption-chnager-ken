import os
import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait

# --- CONFIGURATION (Railway Variables) ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split()]

# Default Caption Format
DEFAULT_CAPTION = """<b><blockquote>💫 {anime_name} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

# Temporary Storage
video_queue = {}
user_captions = {}

app = Client("KenshinAutoBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- CORE LOGIC: INFO EXTRACTION ---
def extract_info(text, filename=""):
    content = f"{text} {filename}".replace("_", " ").replace(".", " ")
    
    # Regex for Anime Name, Episode, Season, Quality
    anime_match = re.search(r'(?i)(?:ᴀɴɪᴍᴇ|Anime)[\s\:\-]*([^\n\r━|\[]+)', content)
    ep_match = re.search(r'(?i)(?:Episode|Ep|S\d+E|E|EPISODE\s*-)[\s\:\-]*(\d+)', content)
    season_match = re.search(r'(?i)(?:Season|S|S0)[\s\:\-]*(\d+)', content)
    quality_match = re.search(r'(\d{3,4}p|4k|2160p)', content)

    anime_name = anime_match.group(1).strip() if anime_match else "Unknown Anime"
    ep = ep_match.group(1).zfill(2) if ep_match else "01"
    season = season_match.group(1).zfill(2) if season_match else "01"
    quality = quality_match.group(1).upper() if quality_match else "Unknown"

    return {"anime_name": anime_name, "ep": ep, "season": season, "quality": quality}

def sort_key(item):
    # Sorting purely based on Episode number
    try:
        return int(item['info']['ep'])
    except:
        return 0

# --- COMMANDS ---
@app.on_message(filters.command("start") & filters.user(ADMINS))
async def start(c, m):
    await m.reply_text(
        f"👋 **Hi {m.from_user.mention}!**\n\n"
        "Main ek advanced Video Processor bot hu jo queueing aur sorting support karta hai.\n\n"
        "🚀 **Kaise use karein?**\n"
        "1. Saari videos ek saath bhej do.\n"
        "2. Ek **Photo** bhejo (wo thumbnail ban jayegi).\n"
        "3. Bot automatic sort karke process shuru kar dega.\n\n"
        "💡 Baaki commands ke liye `/help` dekhein.",
        parse_mode=enums.ParseMode.HTML
    )

@app.on_message(filters.command("help") & filters.user(ADMINS))
async def help_cmd(c, m):
    help_text = """
🔧 **Bot Commands & Usage:**

1️⃣ **Video Queuing:** Kisi bhi video ko forward ya upload karo, bot usey memory mein save kar lega.
2️⃣ **Set Caption:** Naya format set karne ke liye:
   `/set_caption {anime_name} | Ep {ep} | {quality}`
   *(Placeholders: {anime_name}, {ep}, {season}, {quality})*
3️⃣ **Processing:** Jaise hi aap ek **Photo** bhejenge, process start ho jayega.
4️⃣ **Clear Queue:** `/clear` command se pending videos delete karein.

⚠️ **Note:** Thumbnail change karne ke liye Photo bhejna zaroori hai.
    """
    await m.reply_text(help_text)

@app.on_message(filters.command("set_caption") & filters.user(ADMINS))
async def set_cap(c, m):
    if len(m.command) < 2:
        return await m.reply("❌ **Format missing!**\nExample: `/set_caption My Anime - {ep} [{quality}]`")
    
    new_cap = m.text.split(" ", 1)[1]
    user_captions[m.from_user.id] = new_cap
    await m.reply(f"✅ **Custom Caption Saved!**\n\n`{new_cap}`")

@app.on_message(filters.command("clear") & filters.user(ADMINS))
async def clear_queue(c, m):
    video_queue[m.from_user.id] = []
    await m.reply("🗑 **Queue cleared successfully!**")

# --- VIDEO HANDLER ---
@app.on_message((filters.video | filters.document) & filters.user(ADMINS))
async def collect_videos(c, m):
    user_id = m.from_user.id
    if user_id not in video_queue:
        video_queue[user_id] = []
    
    media = m.video or m.document
    # Only allow videos or video-documents
    if m.document and not m.document.mime_type.startswith("video/"):
        return

    info = extract_info(m.caption or "", media.file_name or "")
    
    video_queue[user_id].append({
        "file_id": media.file_id,
        "info": info,
        "file_name": media.file_name or "video.mp4"
    })
    
    tmp = await m.reply_text(f"📥 **Added:** `{info['ep']}` | Queue: **{len(video_queue[user_id])}**", quote=True)
    await asyncio.sleep(3)
    await tmp.delete()

# --- PHOTO HANDLER (THE TRIGGER) ---
@app.on_message(filters.photo & filters.user(ADMINS))
async def process_trigger(c, m):
    user_id = m.from_user.id
    if user_id not in video_queue or not video_queue[user_id]:
        return await m.reply("❌ **Queue khaali hai!** Pehle kuch videos bhejo.")

    status = await m.reply("⏳ **Processing...**\nSorting episodes and downloading thumbnail.")
    
    # Download photo to use as thumb
    thumb_path = await m.download()
    
    # Sort the queue by Episode Number
    video_queue[user_id].sort(key=sort_key)
    
    cap_format = user_captions.get(user_id, DEFAULT_CAPTION)
    count = 0
    total = len(video_queue[user_id])

    for item in video_queue[user_id]:
        try:
            count += 1
            info = item["info"]
            new_caption = cap_format.format(
                anime_name=info["anime_name"],
                ep=info["ep"],
                season=info["season"],
                quality=info["quality"]
            )
            
            await status.edit(f"🚀 **Sending Video {count} of {total}**\nEP: `{info['ep']}`")
            
            await c.send_video(
                chat_id=m.chat.id,
                video=item["file_id"],
                caption=new_caption,
                thumb=thumb_path, # Fixed: Using local path
                parse_mode=enums.ParseMode.HTML
            )
            
            # Anti-flood delay
            await asyncio.sleep(2)
            
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            await m.reply(f"❌ Error in EP {item['info']['ep']}: `{e}`")

    # Cleanup
    if os.path.exists(thumb_path):
        os.remove(thumb_path)
    video_queue[user_id] = []
    
    await status.edit(f"✅ **All Done!**\nTotal **{total}** videos processed and sent in sorted order.")

# --- RUN BOT ---
print("Bot is alive...")
app.run()
