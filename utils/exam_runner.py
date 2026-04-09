import json
import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.db import (
    get_exam, get_topic, update_exam_status,
    get_exam_leaderboard
)

logger = logging.getLogger(__name__)

async def start_exam(application, exam_id):
    """Called by scheduler to start an exam"""
    try:
        exam = get_exam(exam_id)
        if not exam or exam['status'] != 'pending':
            logger.warning(f"Exam {exam_id} not found or not pending")
            return

        topic = get_topic(exam['topic_id'])
        questions = json.loads(exam['questions_json'])
        chat_id = exam['chat_id']
        exam_type = exam['exam_type']

        update_exam_status(exam_id, 'active')

        # Announcement message
        duration = exam['duration_minutes']
        topic_title = topic['title'] if topic else "বিশেষ পরীক্ষা"

        announcement = (
            f"📝 *পরীক্ষা শুরু হচ্ছে!*\n\n"
            f"📚 বিষয়: *{topic_title}*\n"
            f"❓ প্রশ্ন সংখ্যা: *{len(questions)}*\n"
            f"⏱ সময়: *{duration} মিনিট*\n"
            f"📊 ধরন: *{'MCQ' if exam_type == 'mcq' else 'লিখিত'}*\n\n"
            f"{'MCQ প্রশ্নে A, B, C বা D বাটনে ক্লিক করুন' if exam_type == 'mcq' else 'প্রশ্নের উত্তর টাইপ করে পাঠান'}\n\n"
            f"⚠️ প্রতিটি প্রশ্নের উত্তর একবারই দেওয়া যাবে!"
        )

        await application.bot.send_message(
            chat_id=chat_id,
            text=announcement,
            parse_mode='Markdown'
        )

        # Send each question
        for i, q in enumerate(questions, 1):
            if exam_type == 'mcq':
                await send_mcq_question(application, chat_id, exam_id, q, i, len(questions))
            else:
                await send_written_question(application, chat_id, exam_id, q, i, len(questions))

        logger.info(f"Exam {exam_id} started successfully")

    except Exception as e:
        logger.error(f"Error starting exam {exam_id}: {e}")

async def send_mcq_question(application, chat_id, exam_id, question, num, total):
    """Send a single MCQ question with inline buttons"""
    options = question.get('options', {})
    text = (
        f"❓ *প্রশ্ন {num}/{total}*\n\n"
        f"{question['question']}\n\n"
        f"🅰️ {options.get('A', '')}\n"
        f"🅱️ {options.get('B', '')}\n"
        f"🅲 {options.get('C', '')}\n"
        f"🅳 {options.get('D', '')}"
    )

    # Inline keyboard for answers
    keyboard = [
        [
            InlineKeyboardButton("A", callback_data=f"ans_{exam_id}_{question['id']}_A"),
            InlineKeyboardButton("B", callback_data=f"ans_{exam_id}_{question['id']}_B"),
            InlineKeyboardButton("C", callback_data=f"ans_{exam_id}_{question['id']}_C"),
            InlineKeyboardButton("D", callback_data=f"ans_{exam_id}_{question['id']}_D"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def send_written_question(application, chat_id, exam_id, question, num, total):
    """Send a written question"""
    text = (
        f"✍️ *প্রশ্ন {num}/{total}*\n\n"
        f"{question['question']}\n\n"
        f"💡 উত্তর লিখুন এবং পাঠান\n"
        f"_(প্রশ্ন নম্বর দিয়ে শুরু করুন, যেমন: Q{question['id']}: আপনার উত্তর)_"
    )

    await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode='Markdown'
    )

async def end_exam(application, exam_id):
    """Called by scheduler to end an exam"""
    try:
        exam = get_exam(exam_id)
        if not exam or exam['status'] != 'active':
            return

        update_exam_status(exam_id, 'ended')
        chat_id = exam['chat_id']

        # Get leaderboard
        results = get_exam_leaderboard(exam_id)

        if not results:
            await application.bot.send_message(
                chat_id=chat_id,
                text="⏰ পরীক্ষা শেষ!\n\nকোনো অংশগ্রহণকারী পাওয়া যায়নি।",
                parse_mode='Markdown'
            )
            return

        # Build result message
        msg = "⏰ *পরীক্ষা শেষ! ফলাফল:*\n\n"
        medals = ["🥇", "🥈", "🥉"]

        for i, r in enumerate(results[:10], 1):
            medal = medals[i-1] if i <= 3 else f"{i}."
            name = r['full_name'] or r['username'] or "অজানা"
            accuracy = round((r['correct_answers'] / r['total_questions']) * 100) if r['total_questions'] > 0 else 0
            msg += f"{medal} *{name}*\n"
            msg += f"    স্কোর: {r['score']} | সঠিক: {r['correct_answers']}/{r['total_questions']} ({accuracy}%)\n\n"

        total_participants = len(results)
        msg += f"👥 মোট অংশগ্রহণকারী: *{total_participants}*\n"
        msg += f"\n📊 বিস্তারিত দেখতে: /leaderboard"

        await application.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode='Markdown'
        )

        logger.info(f"Exam {exam_id} ended. {total_participants} participants.")

    except Exception as e:
        logger.error(f"Error ending exam {exam_id}: {e}")
