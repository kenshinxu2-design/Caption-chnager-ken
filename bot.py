import os
import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMINS = [int(x) for x in os.environ.get("ADMINS", "0").split()]

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

# Storage: {user_id: [list of video objects]}
video_queue = {}
user_captions = {}

app = Client("KenshinAutoBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- CORE LOGIC ---
def extract_info(text, filename=""):
    content = f"{text} {filename}"
    # Regex for Anime Name, Episode, Season, Quality
    anime_match = re.search(r'(?i)(?:ᴀɴɪᴍᴇ|Anime)[\s\:\-]*([^\n\r━]+)', content)
    ep_match = re.search(r'(?i)(?:Episode|Ep|Episode\s*-)[\s\:\-]*(\d+)', content)
    season_match = re.search(r'(?i)(?:Season|S|S0)[\s\:\-]*(\d+)', content)
    quality_match = re.search(r'(?i)(\d{3,4}p|4k|2160p)', content)

    anime_name = anime_match.group(1).strip() if anime_match else "Unknown"
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
    await m.reply("<blockquote> Jinda hu abhi.. </blockquote>", parse_mode=enums.ParseMode.HTML)

@app.on_message(filters.command("set_caption") & filters.user(ADMINS))
async def set_cap(c, m):
    if len(m.command) < 2:
        return await m.reply("Bahi format bhej! Example:\n`/set_caption {anime_name} - Season {season} - Ep {ep} [{quality}]`")
    new_cap = m.text.split(" ", 1)[1]
    user_captions[m.from_user.id] = new_cap
    await m.reply("✅ **Naya Caption Format Save Ho Gaya!**")

@app.on_message((filters.video | filters.document) & filters.user(ADMINS))
async def collect_videos(c, m):
    user_id = m.from_user.id
    if user_id not in video_queue:
        video_queue[user_id] = []
    
    file_name = m.video.file_name if m.video else m.document.file_name
    info = extract_info(m.caption or "", file_name or "")
    
    video_queue[user_id].append({"msg_id": m.id, "info": info})
    # Chota sa confirmation message delete hone wala (optional)
    tmp = await m.reply(f"📥 Added! Queue: **{len(video_queue[user_id])}**", quote=True)
    await asyncio.sleep(3)
    await tmp.delete()

@app.on_message(filters.command("process") & filters.user(ADMINS))
async def process(c, m):
    user_id = m.from_user.id
    if user_id not in video_queue or not video_queue[user_id]:
        return await m.reply("Bahi pehle videos toh bhej queue mein!")

    status = await m.reply(f"⏳ **Processing {len(video_queue[user_id])} videos...**\nSorting and Sending in progress.")
    
    # Advanced Sorting Logic
    video_queue[user_id].sort(key=sort_key)
    
    cap_format = user_captions.get(user_id, DEFAULT_CAPTION)
    count = 0

    for item in video_queue[user_id]:
        info = item["info"]
        try:
            # Custom placeholders ko replace karna
            new_cap = cap_format.format(
                anime_name=info["anime_name"],
                ep=info["ep"],
                season=info["season"],
                quality=info["quality"]
            )
            
            await c.copy_message(
                chat_id=user_id,
                from_chat_id=user_id,
                message_id=item["msg_id"],
                caption=new_cap,
                parse_mode=enums.ParseMode.HTML
            )
            count += 1
            await asyncio.sleep(1.5) # Flood wait avoid karne ke liye
        except Exception as e:
            print(f"Error: {e}")
            continue

    video_queue[user_id] = [] # Queue clear
    await status.edit(f"✅ **Kaam Ho Gaya!**\nTotal **{count}** videos sort aur rename karke bhej di gayi hain.")

@app.on_message(filters.command("clear") & filters.user(ADMINS))
async def clear_queue(c, m):
    video_queue[m.from_user.id] = []
    await m.reply("🗑 Queue clear ho gayi!")

app.run()
