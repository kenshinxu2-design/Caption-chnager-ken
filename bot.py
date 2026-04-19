import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode

# Config
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

app = Client("KenshinModeBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# Global Storage
video_queue = []
is_processing = False
target_sticker = None 
EXTRACTION_MODE = "caption" # Default: caption | filename
CUSTOM_CAPTION = """<b><blockquote>💫 {anime_name} 💫</blockquote>
‣ Episode : {ep}
‣ Season : {season}
‣ Quality : {quality}
‣ Audio : Hindi Dub 🎙️ | Official
━━━━━━━━━━━━━━━━━━━━━
<blockquote>🚀 For More Join
🔰 [@KENSHIN_ANIME]</blockquote>
━━━━━━━━━━━━━━━━━━━━━</b>"""

def get_quality_rank(q_str):
    ranks = {"480p": 1, "720p": 2, "1080p": 3, "4k": 4, "2160p": 5}
    return ranks.get(q_str.lower(), 0)

# --- Commands ---

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply("<blockquote>Jinda hu abhi....</blockquote>")

@app.on_message(filters.command("set_mode") & filters.user(ADMIN_ID))
async def set_mode_cmd(client, message: Message):
    global EXTRACTION_MODE
    if len(message.command) > 1:
        mode = message.command[1].lower()
        if mode in ["caption", "filename"]:
            EXTRACTION_MODE = mode
            await message.reply(f"✅ <b>Extraction Mode set to:</b> <code>{EXTRACTION_MODE}</code>")
        else:
            await message.reply("❌ <b>Galat Mode!</b> Use: <code>/set_mode caption</code> OR <code>filename</code>")
    else:
        await message.reply(f"ℹ️ <b>Current Mode:</b> <code>{EXTRACTION_MODE}</code>\nChange it using <code>/set_mode [caption/filename]</code>")

@app.on_message(filters.command("set_sticker") & filters.reply & filters.user(ADMIN_ID))
async def set_sticker_cmd(client, message: Message):
    global target_sticker
    if message.reply_to_message.sticker:
        target_sticker = message.reply_to_message.sticker.file_id
        await message.reply("✅ <b>Sticker Set!</b>")

@app.on_message(filters.command("set_caption") & filters.user(ADMIN_ID))
async def set_caption_cmd(client, message: Message):
    global CUSTOM_CAPTION
    if len(message.command) > 1:
        CUSTOM_CAPTION = message.text.split(None, 1)[1]
        await message.reply(f"✅ <b>Custom Caption Set!</b>")
    else:
        await message.reply("❌ Use: <code>/set_caption [text]</code>")

@app.on_message(filters.command("cancel_queue") & filters.user(ADMIN_ID))
async def cancel_queue_cmd(client, message: Message):
    global video_queue, is_processing
    video_queue = []
    is_processing = False
    await message.reply("🛑 <b>Queue Cancelled!</b>")

# --- Universal Extraction Logic ---

def extract_data(text):
    # Season Detection
    season_match = re.search(r"(?i)(?:Season|S)[\s\-:]*(\d+)", text)
    season = season_match.group(1).zfill(2) if season_match else "01"

    # Episode Detection
    ep_match = re.search(r"(?i)(?:Episode|Ep|E)[\s\-:]*(\d+)", text)
    ep_num = int(ep_match.group(1)) if ep_match else 0
    ep_str = str(ep_num).zfill(2)

    # Quality Detection
    quality_match = re.search(r"(?i)(1080p|720p|480p|360p|4K|2160p)", text)
    quality = quality_match.group(1) if quality_match else "HD"

    # Anime Name Logic (Simplified for FileNames)
    name_match = re.search(r"(?i)(?:ᴀɴɪᴍᴇ|Anime|Name|📟)[\s\-:]*([^\n|(\-]+)", text)
    if name_match:
        anime_name = name_match.group(1).strip()
    else:
        # File name se tags hata kar name nikalna
        clean_text = re.sub(r"\[.*?\]|\(.*?\)|@\w+", "", text).strip()
        anime_name = clean_text.split('.')[0][:25] if clean_text else "Anime"

    return anime_name, ep_str, ep_num, season, quality

# --- Processing Logic ---

async def process_queue(client, chat_id):
    global is_processing, video_queue, target_sticker, CUSTOM_CAPTION
    is_processing = True
    video_queue.sort(key=lambda x: (x['ep_num'], x['q_rank']))
    
    status_msg = await client.send_message(chat_id, "🚀 <b>Processing in Sequence...</b>")

    last_ep = None
    for item in video_queue:
        if not is_processing: break
        msg = item['message']
        
        if last_ep is not None and item['ep_num'] != last_ep:
            if target_sticker:
                await client.send_sticker(chat_id, target_sticker)
            last_ep = item['ep_num']

        try:
            f_id = msg.video.file_id if msg.video else msg.document.file_id
            await client.send_video(
                chat_id=chat_id,
                video=f_id,
                caption=CUSTOM_CAPTION.format(
                    anime_name=item['name'], ep=item['ep_str'], 
                    season=item['season'], quality=item['quality']
                ),
                parse_mode=ParseMode.HTML,
                supports_streaming=True
            )
            await msg.delete()
            await asyncio.sleep(0.6)
        except Exception as e:
            print(f"Error: {e}")

    if is_processing and target_sticker:
        await client.send_sticker(chat_id, target_sticker)

    await status_msg.edit("✅ <b>Queue Cleared!</b>")
    video_queue = []
    is_processing = False

@app.on_message((filters.video | filters.document) & filters.private & filters.user(ADMIN_ID))
async def collector(client, message: Message):
    global video_queue, EXTRACTION_MODE
    
    # Mode ke hisaab se text pick karna
    if EXTRACTION_MODE == "filename":
        file_obj = message.video or message.document
        search_text = file_obj.file_name if file_obj else ""
    else:
        search_text = message.caption or ""

    name, ep_str, ep_num, season, quality = extract_data(search_text)

    video_queue.append({
        'message': message,
        'name': name,
        'ep_str': ep_str,
        'ep_num': ep_num,
        'season': season,
        'quality': quality,
        'q_rank': get_quality_rank(quality)
    })

    if not is_processing:
        await asyncio.sleep(4)
        if not is_processing and video_queue:
            await process_queue(client, message.chat.id)

app.run()
