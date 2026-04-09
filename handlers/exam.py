import json
import logging
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_active_exam, get_participant, save_participant,
    get_exam_leaderboard, get_weekly_leaderboard,
    get_monthly_leaderboard, get_alltime_leaderboard, get_exam
)
from utils.ai_generator import evaluate_written_answer

logger = logging.getLogger(__name__)

# Track user answer sessions: {user_id: {exam_id, answers, start_time}}
user_sessions = {}

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle both MCQ (callback) and written answers"""

    if update.callback_query:
        await handle_mcq_answer(update, context)
    elif update.message and update.message.text:
        await handle_written_answer(update, context)

async def handle_mcq_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle MCQ button click"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("ans_"):
        return

    parts = data.split("_")
    if len(parts) != 4:
        return

    _, exam_id, question_id, chosen = parts
    exam_id = int(exam_id)
    question_id = int(question_id)
    user = query.from_user
    user_id = user.id

    # Check if exam is still active
    exam = get_exam(exam_id)
    if not exam or exam['status'] != 'active':
        await query.answer("⚠️ এই পরীক্ষা আর সক্রিয় নেই।", show_alert=True)
        return

    # Initialize session
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    if exam_id not in user_sessions[user_id]:
        user_sessions[user_id][exam_id] = {
            'answers': {},
            'start_time': time.time()
        }

    session = user_sessions[user_id][exam_id]

    # Check if already answered this question
    if str(question_id) in session['answers']:
        await query.answer("⚠️ এই প্রশ্নের উত্তর আগেই দিয়েছেন।", show_alert=True)
        return

    # Record answer
    session['answers'][str(question_id)] = chosen

    # Check answer
    questions = json.loads(exam['questions_json'])
    question = next((q for q in questions if q['id'] == question_id), None)
    if not question:
        return

    correct = question['correct_answer']
    is_correct = chosen == correct
    explanation = question.get('explanation', '')

    if is_correct:
        result_text = f"✅ সঠিক! +10 পয়েন্ট\n\n💡 {explanation}"
    else:
        result_text = f"❌ ভুল! সঠিক উত্তর: **{correct}**\n\n💡 {explanation}"

    await query.answer(result_text[:200], show_alert=True)

    # Check if all questions answered
    total_questions = len(questions)
    answered = len(session['answers'])

    if answered >= total_questions:
        await finalize_mcq_submission(context, user, exam_id, exam, questions, session)

async def finalize_mcq_submission(context, user, exam_id, exam, questions, session):
    """Calculate final score and save"""
    answers = session['answers']
    correct_count = 0
    score = 0

    for q in questions:
        user_ans = answers.get(str(q['id']))
        if user_ans == q['correct_answer']:
            correct_count += 1
            score += 10

    time_taken = int(time.time() - session['start_time'])
    total = len(questions)

    # Save to DB
    saved = save_participant(
        exam_id=exam_id,
        user_id=user.id,
        username=user.username or "",
        full_name=user.full_name or user.username or "অজানা",
        answers_json=json.dumps(answers),
        score=score,
        total_questions=total,
        correct_answers=correct_count,
        time_taken=time_taken
    )

    accuracy = round((correct_count / total) * 100) if total > 0 else 0
    minutes = time_taken // 60
    seconds = time_taken % 60

    msg = (
        f"🎯 *আপনার ফলাফল*\n\n"
        f"👤 {user.full_name}\n"
        f"✅ সঠিক: {correct_count}/{total}\n"
        f"📊 নির্ভুলতা: {accuracy}%\n"
        f"🏆 স্কোর: {score} পয়েন্ট\n"
        f"⏱ সময়: {minutes}মি {seconds}সে"
    )

    if accuracy >= 80:
        msg += "\n\n🌟 অসাধারণ!"
    elif accuracy >= 60:
        msg += "\n\n👍 ভালো করেছেন!"
    else:
        msg += "\n\n📚 আরও পড়াশোনা করুন!"

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=msg,
            parse_mode='Markdown'
        )
    except Exception:
        # If can't DM, send to group
        chat_id = exam['chat_id']
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ {user.full_name} পরীক্ষা সম্পন্ন করেছেন! স্কোর: {score}",
            parse_mode='Markdown'
        )

    # Clear session
    if user.id in user_sessions and exam_id in user_sessions[user.id]:
        del user_sessions[user.id][exam_id]

async def handle_written_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle written answer submission"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # Check format: Q1: answer
    if not text.upper().startswith("Q"):
        return

    # Find active exam in this chat
    exam = get_active_exam(chat_id)
    if not exam or exam['exam_type'] != 'written':
        return

    # Parse question number
    try:
        colon_pos = text.index(":")
        q_part = text[:colon_pos].strip().upper()
        q_num = int(q_part[1:])
        user_answer = text[colon_pos+1:].strip()
    except (ValueError, IndexError):
        return

    exam_id = exam['id']
    questions = json.loads(exam['questions_json'])
    question = next((q for q in questions if q['id'] == q_num), None)

    if not question:
        await update.message.reply_text(f"❌ Q{q_num} নামে কোনো প্রশ্ন নেই।")
        return

    # Initialize session
    user_id = user.id
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    if exam_id not in user_sessions[user_id]:
        user_sessions[user_id][exam_id] = {'answers': {}, 'start_time': time.time()}

    session = user_sessions[user_id][exam_id]

    if str(q_num) in session['answers']:
        await update.message.reply_text(f"⚠️ Q{q_num}-এর উত্তর আগেই দিয়েছেন।")
        return

    # Evaluate with AI
    wait = await update.message.reply_text("⏳ উত্তর যাচাই করা হচ্ছে...")

    evaluation = evaluate_written_answer(
        question=question['question'],
        model_answer=question['model_answer'],
        keywords=question.get('keywords', []),
        user_answer=user_answer
    )

    points = question.get('points', 20)
    earned = int(points * evaluation['score_percentage'] / 100)

    session['answers'][str(q_num)] = {
        'answer': user_answer,
        'score': earned,
        'evaluation': evaluation
    }

    result_msg = (
        f"📝 *Q{q_num} ফলাফল*\n\n"
        f"{'✅ সঠিক' if evaluation['is_correct'] else '⚠️ আংশিক/ভুল'}\n"
        f"💬 {evaluation['feedback']}\n"
        f"🏆 পয়েন্ট: {earned}/{points}"
    )

    await wait.edit_text(result_msg, parse_mode='Markdown')

    # Check if all answered
    if len(session['answers']) >= len(questions):
        total_score = sum(
            v['score'] if isinstance(v, dict) else 0
            for v in session['answers'].values()
        )
        correct = sum(
            1 for v in session['answers'].values()
            if isinstance(v, dict) and v.get('evaluation', {}).get('is_correct', False)
        )
        time_taken = int(time.time() - session['start_time'])

        save_participant(
            exam_id=exam_id,
            user_id=user_id,
            username=user.username or "",
            full_name=user.full_name or "অজানা",
            answers_json=json.dumps(session['answers']),
            score=total_score,
            total_questions=len(questions),
            correct_answers=correct,
            time_taken=time_taken
        )

        await update.message.reply_text(
            f"🎯 *সব প্রশ্নের উত্তর দিয়েছেন!*\n\n"
            f"মোট স্কোর: *{total_score}*\n"
            f"সঠিক: *{correct}/{len(questions)}*",
            parse_mode='Markdown'
        )

        del user_sessions[user_id][exam_id]

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show leaderboard options"""
    args = context.args
    lb_type = args[0].lower() if args else 'alltime'

    if lb_type == 'weekly':
        rows = get_weekly_leaderboard()
        title = "📅 সাপ্তাহিক লিডারবোর্ড"
    elif lb_type == 'monthly':
        rows = get_monthly_leaderboard()
        title = "🗓 মাসিক লিডারবোর্ড"
    else:
        rows = get_alltime_leaderboard()
        title = "🏆 সর্বকালীন লিডারবোর্ড"

    if not rows:
        await update.message.reply_text("এখনো কোনো তথ্য নেই।")
        return

    medals = ["🥇", "🥈", "🥉"]
    msg = f"*{title}*\n\n"

    for i, r in enumerate(rows, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        name = r['full_name'] or r['username'] or "অজানা"

        if lb_type == 'alltime':
            total_q = r['total_questions_answered']
            accuracy = round((r['total_correct'] / total_q) * 100) if total_q > 0 else 0
            msg += (f"{medal} *{name}*\n"
                    f"    স্কোর: {r['total_score']} | "
                    f"পরীক্ষা: {r['total_exams']} | "
                    f"নির্ভুলতা: {accuracy}%\n\n")
        else:
            total_q = r['total_questions']
            accuracy = round((r['total_correct'] / total_q) * 100) if total_q > 0 else 0
            msg += (f"{medal} *{name}*\n"
                    f"    স্কোর: {r['total_score']} | "
                    f"পরীক্ষা: {r['exams_taken']} | "
                    f"নির্ভুলতা: {accuracy}%\n\n")

    msg += (
        "\n📌 অন্য লিডারবোর্ড:\n"
        "/leaderboard weekly\n"
        "/leaderboard monthly\n"
        "/leaderboard alltime"
    )

    await update.message.reply_text(msg, parse_mode='Markdown')
