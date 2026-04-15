import os
import uuid
import shutil
from fpdf import FPDF
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from faster_whisper import WhisperModel

TOKEN = os.getenv("TELEGRAM_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

print("Loading Whisper model...")
model = WhisperModel("tiny", device="cpu", compute_type="int8")
print("Model loaded")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    if not url.startswith("http"):
        await update.message.reply_text("Send a valid video link.")
        return

    await update.message.reply_text(
        "Downloading audio and generating transcript PDF..."
    )

    work_dir = os.path.join(TEMP_DIR, str(uuid.uuid4()))
    os.makedirs(work_dir, exist_ok=True)

    try:
        audio_template = os.path.join(work_dir, "audio.%(ext)s")

        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
            "outtmpl": audio_template,
            "quiet": True,
            "noplaylist": True,
            "http_headers": {
    "Cookie": "csrftoken=WNbUUWIrOMKghZYvyCjPYJ7Zl6qPrlb5; datr=CE3faf-Z41g60V94lw4SOuQ5; ig_did=66BB6425-A7E9-4CE1-A9AE-2C7297C4CF7C; wd=407x749; dpr=3; mid=ad9NCAABAAFu2dODn7VSV7N9khZk; ds_user_id=45531100817; sessionid=45531100817%3A5FaXkPcY943bDh%3A27%3AAYggQzD62sUwrxVNOhTfvCwFPQyffZxRbo9fXjYMig; ps_l=1; ps_n=1; rur=\"PRN\\05445531100817\\0541807778429:01fea753bcde8fd32bd931e357d1ae68c514c8ddf1b1097f13030db8020f8c110d09127a\";"
},
            "postprocessors": []
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)

        segments, _ = model.transcribe(downloaded_file)

        transcript = " ".join(
            segment.text.strip() for segment in segments
        ).strip()

        if not transcript:
            transcript = "No speech detected in the provided media."

        title = info.get("title", "Transcript")
        safe_title = "".join(
            c for c in title if c.isalnum() or c in " _-"
        ).strip()

        if not safe_title:
            safe_title = "Transcript"

        pdf_path = os.path.join(work_dir, f"{safe_title}.pdf")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        font_path = os.path.join(
            os.path.dirname(__file__),
            "NotoSans-Regular.ttf"
        )
        pdf.add_font("Noto", "", font_path)
        pdf.add_page()

        pdf.set_font("Noto", size=16)
        pdf.multi_cell(0, 10, title)
        pdf.ln(4)

        pdf.set_font("Noto", size=12)

        for paragraph in transcript.split(". "):
            pdf.multi_cell(0, 8, paragraph.strip())
            pdf.ln(1)

        pdf.output(pdf_path)

        with open(pdf_path, "rb") as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename=f"{safe_title}.pdf",
                caption=f"Transcript generated for: {title}"
            )

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
)

print("Bot running...")
app.run_polling()