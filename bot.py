import os
import uuid
import shutil
import subprocess
from fpdf import FPDF
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import whisper

TOKEN = os.getenv("TELEGRAM_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

model = whisper.load_model("base")

class UnicodePDF(FPDF):
    pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    if not url.startswith("http"):
        await update.message.reply_text("Send a valid video link.")
        return

    await update.message.reply_text("Downloading and generating transcript PDF...")

    work_dir = os.path.join(TEMP_DIR, str(uuid.uuid4()))
    os.makedirs(work_dir, exist_ok=True)

    try:
        video_path = os.path.join(work_dir, "video.mp4")
        audio_path = os.path.join(work_dir, "audio.mp3")
        pdf_path = os.path.join(work_dir, "transcript.pdf")

        with YoutubeDL({
            "outtmpl": video_path,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "quiet": True
        }) as ydl:
            ydl.download([url])

        subprocess.run([
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "mp3", "-y", audio_path
        ], check=True)

        result = model.transcribe(audio_path)
        text = result["text"].strip() or "No speech detected."

        pdf = UnicodePDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        for line in text.split(". "):
            pdf.multi_cell(0, 8, line)

        pdf.output(pdf_path)

        with open(pdf_path, "rb") as f:
            await update.message.reply_document(f, filename="transcript.pdf")

    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
