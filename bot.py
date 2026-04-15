import os
import uuid
import shutil
import subprocess
from fpdf import FPDF
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import whisper

TOKEN = os.getenv("TELEGRAM_TOKEN", "8506215613:AAFDt3udjpTJBJFsEzv6r7zHlTCG29hvhsQ")

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

print("Loading Whisper model...")
model = whisper.load_model("base")
print("Whisper model loaded")


class UnicodePDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "Video Transcript", ln=True, align="C")
        self.ln(5)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    if not url.startswith("http"):
        await update.message.reply_text(
            "Send a valid video link. Example: YouTube, Vimeo, direct MP4, etc."
        )
        return

    await update.message.reply_text("Downloading video and converting speech to PDF. This may take a few minutes...")

    unique_id = str(uuid.uuid4())
    work_dir = os.path.join(TEMP_DIR, unique_id)
    os.makedirs(work_dir, exist_ok=True)

    try:
        video_path = os.path.join(work_dir, "video.mp4")
        audio_path = os.path.join(work_dir, "audio.mp3")
        pdf_path = os.path.join(work_dir, "transcript.pdf")

        ydl_opts = {
            "outtmpl": video_path,
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "quiet": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vn",
                "-acodec",
                "mp3",
                "-y",
                audio_path,
            ],
            check=True,
        )

        result = model.transcribe(audio_path)
        transcript = result["text"].strip()

        if not transcript:
            transcript = "No speech detected in the video."

        pdf = UnicodePDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        # Break long transcript into lines
        for line in transcript.split(". "):
            pdf.multi_cell(0, 8, line.strip())
            pdf.ln(1)

        pdf.output(pdf_path)

        with open(pdf_path, "rb") as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="transcript.pdf",
                caption="Transcript PDF generated successfully"
            )

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Bot running...")
app.run_polling()
