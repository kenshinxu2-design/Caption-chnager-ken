import os
import re
import asyncio
from pyrogram import Client, filters, enums

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "1234567")) # Apna API ID daalo
API_HASH = os.environ.get("API_HASH", "your_api_hash") # Apna API Hash daalo
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
ADMINS = [int(x) for x in os.environ.get("ADMINS", "123456789").split()] # Apna User ID daalo

# Default Caption Format
DEFAULT_CAPTION = """<b><blockquote>💫 {anime_name} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

# Storage dictionaries
video_queue = {}
user_captions = {}

app = Client("KenshinMixedBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- CORE LOGIC ---
def extract_info(text, filename=""):
    content = f"{text} {filename}"
    
    # Regex for Anime Name, Episode, Season, Quality
    anime_match = re.search(r'(?i)(?:ᴀɴɪᴍᴇ|Anime)[\s\:\-]*([^\n\r━]+)', content)
    ep_match = re.search(r'(?i)(?:Episode|Ep|Episode\s*-)[\s\:\-]*(\d+)', content)
    season_match = re.search(r'(?i)(?:Season|S|S0)[\s\:\-]*(\d+)', content)
    quality_match = re.search(r'(?i)(\d{3,4}p|4k|2160p)', content)

    anime_name = anime_match.group(1).strip() if anime_match else "Unknown Anime"
    ep = ep_match.group(1).zfill(2) if ep_match else "01"
    season = season_match.group(1).zfill(2) if season_match else "01"
    quality = quality_match.group(1).lower() if quality_match else "Unknown"

    return {"anime_name": anime_name, "ep": ep, "season": season, "quality": quality}

def sort_key(item):
    info = item['info']
    # Sorting by Episode (Numeric) then Quality Score
    ep_num = int(info['ep']) if info['ep'].isdigit() else 0
    q = info['quality']
    q_score = 1 if '480' in q else 2 if '720' in q else 3 if '1080' in q else 4 if ('4k' in q or '2160' in q) else 0
    return (ep_num, q_score)

# --- HANDLERS ---
@app.on_message(filters.command("start") & filters.user(ADMINS))
async def start(c, m):
    await m.reply(
        "🎬 **Advanced Video Processor Bot**\n\n"
        "**Kaam ka tareeka:**\n"
        "1️⃣ Saari videos ek saath bhejo (Queue banegi)\n"
        "2️⃣ Bot automatically unhe sort karega Episode aur Quality ke hisaab se\n"
        "3️⃣ Ek **Photo (Cover/Thumb)** bhejo\n"
        "4️⃣ Bot har video mein naya caption aur thumb laga kar sorted order mein bhej dega!\n\n"
        "Caption format badalne ke liye `/set_caption` use karein."
    )

@app.on_message(filters.command("set_caption") & filters.user(ADMINS))
async def set_cap(c, m):
    if len(m.command) < 2:
        return await m.reply("❌ Bahi format bhej! Example:\n`/set_caption {anime_name} - Season {season} - Ep {ep} [{quality}]`")
    new_cap = m.text.split(" ", 1)[1]
    user_captions[m.from_user.id] = new_cap
    await m.reply("✅ **Naya Caption Format Save Ho Gaya!**")

@app.on_message((filters.video | filters.document) & filters.user(ADMINS))
async def collect_videos(c, m):
    user_id = m.from_user.id
    if user_id not in video_queue:
        video_queue[user_id] = []
    
    # Check if video or document
    vid_obj = m.video or m.document
    if not vid_obj:
        return

    file_name = getattr(vid_obj, "file_name", "")
    info = extract_info(m.caption or "", file_name or "")
    
    video_data = {
        "file_id": vid_obj.file_id,
        "info": info,
        "duration": getattr(vid_obj, "duration", 0),
        "width": getattr(vid_obj, "width", 0),
        "height": getattr(vid_obj, "height", 0)
    }
    
    video_queue[user_id].append(video_data)
    
    # Auto-deleting temp message
    tmp = await m.reply(f"📥 Added! Total Queue: **{len(video_queue[user_id])}**\n📸 Processing start karne ke liye ab ek **Thumbnail Photo** bhejo.", quote=True)
    await asyncio.sleep(4)
    await tmp.delete()

@app.on_message(filters.photo & filters.user(ADMINS))
async def process_and_send(c, m):
    user_id = m.from_user.id
    if user_id not in video_queue or not video_queue[user_id]:
        return await m.reply("❌ Bhai pehle videos toh bhej queue mein! Uske baad thumb bhejna.")

    status = await m.reply(f"⏳ **Thumbnail mil gaya!**\n📥 Downloading thumb and processing **{len(video_queue[user_id])}** videos...")
    
    # Download thumbnail locally
    thumb_path = await m.download()
    
    # Advanced Sorting Logic (Ep & Quality)
    video_queue[user_id].sort(key=sort_key)
    
    cap_format = user_captions.get(user_id, DEFAULT_CAPTION)
    count = 0

    await status.edit(f"⚡ **Processing Start...**\nSorting aur upload chaalu hai!")

    for item in video_queue[user_id]:
        info = item["info"]
        try:
            # Custom placeholders replace karna
            new_cap = cap_format.format(
                anime_name=info["anime_name"],
                ep=info["ep"],
                season=info["season"],
                quality=info["quality"]
            )
            
            # Send video with new thumb and caption
            await c.send_video(
                chat_id=user_id,
                video=item["file_id"],
                thumb=thumb_path, # Naya thumbnail yahan lag gaya
                caption=new_cap,
                duration=item["duration"],
                width=item["width"],
                height=item["height"],
                parse_mode=enums.ParseMode.HTML
            )
            count += 1
            await asyncio.sleep(1.5) # Flood wait avoid karne ke liye
            
        except Exception as e:
            print(f"Error sending video: {e}")
            continue

    # Cleanup
    if os.path.exists(thumb_path):
        os.remove(thumb_path)
    video_queue[user_id] = [] # Queue clear
    
    await status.edit(f"✅ **Kaam Ho Gaya!**\nTotal **{count}** videos sorted, naye caption aur same thumbnail ke saath bhej di gayi hain.")

@app.on_message(filters.command("clear") & filters.user(ADMINS))
async def clear_queue(c, m):
    video_queue[m.from_user.id] = []
    await m.reply("🗑 Queue clear ho gayi! Nayi videos bhejna shuru karo.")

print("Bot is starting...")
app.run()
