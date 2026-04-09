import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database.db import (
    save_topic, get_all_topics, delete_topic, is_admin,
    create_exam, get_active_exam
)
from utils.ai_generator import generate_mcq_questions, generate_written_questions
from utils.scheduler import schedule_exam_job, cancel_exam_jobs
from database.db import get_exam, update_exam_status, get_pending_exams

logger = logging.getLogger(__name__)

def admin_only(func):
    """Decorator to restrict commands to admins"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("❌ এই কমান্ড শুধুমাত্র অ্যাডমিনদের জন্য।")
            return
        return await func(update, context)
    return wrapper

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_adm = is_admin(user.id)

    msg = (
        f"🎓 *পরীক্ষা বট-এ স্বাগতম!*\n\n"
        f"নাম: {user.full_name}\n\n"
    )

    if is_adm:
        msg += (
            "🔧 *অ্যাডমিন কমান্ড:*\n"
            "/addtopic - নতুন টপিক যোগ করুন\n"
            "/topics - সব টপিক দেখুন\n"
            "/schedule - পরীক্ষা শিডিউল করুন\n"
            "/cancelexam - পরীক্ষা বাতিল করুন\n"
            "/stats - পরিসংখ্যান দেখুন\n"
            "/broadcast - সবাইকে বার্তা পাঠান\n\n"
        )

    msg += (
        "👤 *আপনার কমান্ড:*\n"
        "/mystats - আমার পরিসংখ্যান\n"
        "/leaderboard - লিডারবোর্ড দেখুন"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')

@admin_only
async def add_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /addtopic
    Then bot asks for title and content in steps
    """
    context.user_data['adding_topic'] = True
    context.user_data['topic_step'] = 'title'
    await update.message.reply_text(
        "📝 নতুন টপিক যোগ করুন\n\n"
        "প্রথমে *টপিকের শিরোনাম* লিখুন:",
        parse_mode='Markdown'
    )

@admin_only
async def list_topics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topics = get_all_topics()
    if not topics:
        await update.message.reply_text("কোনো টপিক নেই। /addtopic দিয়ে যোগ করুন।")
        return

    msg = "📚 *সকল টপিক:*\n\n"
    for t in topics:
        msg += f"🔹 ID: `{t['id']}` | *{t['title']}*\n"
        msg += f"    যোগ করা: {str(t['created_at'])[:10]}\n\n"

    await update.message.reply_text(msg, parse_mode='Markdown')

@admin_only
async def schedule_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /schedule <topic_id> <type> <datetime> <duration> <num_questions>
    Example: /schedule 1 mcq 2024-01-15 14:30 10 5
    type: mcq or written
    """
    args = context.args
    if len(args) < 5:
        await update.message.reply_text(
            "❌ সঠিক ফরম্যাট:\n"
            "`/schedule <topic_id> <type> <date> <time> <duration_min> <questions>`\n\n"
            "উদাহরণ:\n"
            "`/schedule 1 mcq 2024-01-15 14:30 10 5`\n\n"
            "type: `mcq` অথবা `written`\n"
            "টপিক ID দেখতে: /topics",
            parse_mode='Markdown'
        )
        return

    try:
        topic_id = int(args[0])
        exam_type = args[1].lower()
        date_str = args[2]
        time_str = args[3]
        duration = int(args[4])
        num_questions = int(args[5]) if len(args) > 5 else 5

        if exam_type not in ['mcq', 'written']:
            await update.message.reply_text("❌ type অবশ্যই `mcq` অথবা `written` হতে হবে।")
            return

        scheduled_at = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        if scheduled_at <= datetime.now():
            await update.message.reply_text("❌ শিডিউল সময় ভবিষ্যতে হতে হবে।")
            return

        from database.db import get_topic
        topic = get_topic(topic_id)
        if not topic:
            await update.message.reply_text(f"❌ Topic ID {topic_id} পাওয়া যায়নি। /topics দেখুন।")
            return

        # Generate questions
        wait_msg = await update.message.reply_text("⏳ AI প্রশ্ন তৈরি করছে...")

        if exam_type == 'mcq':
            questions = generate_mcq_questions(topic['content'], num_questions)
        else:
            questions = generate_written_questions(topic['content'], num_questions)

        if not questions:
            await wait_msg.edit_text("❌ প্রশ্ন তৈরি করতে সমস্যা হয়েছে। আবার চেষ্টা করুন।")
            return

        # Determine chat_id (use group chat if command from group, else ask)
        chat_id = update.effective_chat.id

        # Create exam in DB
        questions_json = json.dumps(questions, ensure_ascii=False)
        exam_id = create_exam(topic_id, chat_id, questions_json, exam_type,
                              scheduled_at, duration)

        # Schedule the job
        schedule_exam_job(
            context.application,
            exam_id,
            scheduled_at,
            duration
        )

        await wait_msg.edit_text(
            f"✅ *পরীক্ষা শিডিউল সম্পন্ন!*\n\n"
            f"📚 বিষয়: *{topic['title']}*\n"
            f"📊 ধরন: *{exam_type.upper()}*\n"
            f"❓ প্রশ্ন: *{len(questions)}টি*\n"
            f"⏰ সময়: *{scheduled_at.strftime('%d %b %Y, %I:%M %p')}*\n"
            f"⏱ সময়সীমা: *{duration} মিনিট*\n"
            f"🆔 পরীক্ষা ID: `{exam_id}`",
            parse_mode='Markdown'
        )

    except ValueError as e:
        await update.message.reply_text(f"❌ ইনপুট ভুল: {e}\n\nসঠিক ফরম্যাট দেখুন: /schedule")

@admin_only
async def cancel_exam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /cancelexam <exam_id>"""
    args = context.args
    if not args:
        # Show pending exams
        pending = get_pending_exams()
        if not pending:
            await update.message.reply_text("কোনো পেন্ডিং পরীক্ষা নেই।")
            return
        msg = "⏳ *পেন্ডিং পরীক্ষা:*\n\n"
        for e in pending:
            msg += f"ID: `{e['id']}` | {e['scheduled_at']}\n"
        msg += "\nবাতিল করতে: `/cancelexam <exam_id>`"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return

    try:
        exam_id = int(args[0])
        exam = get_exam(exam_id)
        if not exam:
            await update.message.reply_text(f"❌ Exam ID {exam_id} পাওয়া যায়নি।")
            return

        cancel_exam_jobs(exam_id)
        update_exam_status(exam_id, 'cancelled')
        await update.message.reply_text(f"✅ পরীক্ষা ID `{exam_id}` বাতিল করা হয়েছে।",
                                        parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ সঠিক exam ID দিন।")

@admin_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db import get_conn
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) as cnt FROM exams WHERE status='ended'")
    total_exams = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) as cnt FROM participants")
    total_submissions = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) as cnt FROM user_stats")
    total_users = c.fetchone()['cnt']

    c.execute("SELECT COUNT(*) as cnt FROM topics")
    total_topics = c.fetchone()['cnt']

    conn.close()

    msg = (
        f"📊 *বট পরিসংখ্যান*\n\n"
        f"📚 মোট টপিক: *{total_topics}*\n"
        f"📝 মোট পরীক্ষা: *{total_exams}*\n"
        f"👥 মোট অংশগ্রহণকারী: *{total_users}*\n"
        f"✅ মোট উত্তর জমা: *{total_submissions}*"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /broadcast <message>"""
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <বার্তা>")
        return

    message = ' '.join(context.args)
    chat_id = update.effective_chat.id

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📢 *ঘোষণা:*\n\n{message}",
        parse_mode='Markdown'
    )
