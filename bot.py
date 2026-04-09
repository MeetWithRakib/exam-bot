import logging
import asyncio
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
from handlers.admin import (
    start, add_topic, list_topics, schedule_exam,
    cancel_exam, stats_command, broadcast
)
from handlers.exam import handle_answer, show_leaderboard
from handlers.user import my_stats
from utils.scheduler import setup_scheduler
from database.db import init_db
import os

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def post_init(application):
    await setup_scheduler(application)

def main():
    init_db()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set!")

    app = Application.builder().token(token).post_init(post_init).build()

    # Admin commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtopic", add_topic))
    app.add_handler(CommandHandler("topics", list_topics))
    app.add_handler(CommandHandler("schedule", schedule_exam))
    app.add_handler(CommandHandler("cancelexam", cancel_exam))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # User commands
    app.add_handler(CommandHandler("mystats", my_stats))
    app.add_handler(CommandHandler("leaderboard", show_leaderboard))

    # Exam interactions
    app.add_handler(CallbackQueryHandler(handle_answer))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer))

    logger.info("Bot started successfully!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
