from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_user_stats, get_exam_leaderboard, get_conn

async def my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats = get_user_stats(user.id)

    if not stats:
        await update.message.reply_text(
            "📊 এখনো কোনো পরীক্ষায় অংশ নেননি।\n"
            "পরীক্ষায় অংশ নিন এবং আপনার স্ট্যাটস দেখুন!"
        )
        return

    total_q = stats['total_questions_answered']
    accuracy = round((stats['total_correct'] / total_q) * 100) if total_q > 0 else 0

    # Get rank
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT COUNT(*) + 1 as rank FROM user_stats 
                 WHERE total_score > (SELECT total_score FROM user_stats WHERE user_id = ?)""",
              (user.id,))
    rank_row = c.fetchone()
    rank = rank_row['rank'] if rank_row else 'N/A'
    conn.close()

    msg = (
        f"📊 *আপনার পরিসংখ্যান*\n\n"
        f"👤 নাম: {stats['full_name']}\n"
        f"🏅 সার্বিক র‌্যাংক: #{rank}\n\n"
        f"📝 মোট পরীক্ষা: *{stats['total_exams']}*\n"
        f"✅ মোট সঠিক: *{stats['total_correct']}/{total_q}*\n"
        f"🎯 নির্ভুলতার হার: *{accuracy}%*\n"
        f"🏆 মোট স্কোর: *{stats['total_score']}*\n\n"
        f"📅 শেষ সক্রিয়: {str(stats['last_active'])[:10]}"
    )

    # Performance badge
    if accuracy >= 90:
        msg += "\n\n🌟 *অসাধারণ পারফরম্যান্স!*"
    elif accuracy >= 75:
        msg += "\n\n🔥 *দুর্দান্ত!*"
    elif accuracy >= 60:
        msg += "\n\n👍 *ভালো চলছে!*"
    else:
        msg += "\n\n📚 *আরও পরিশ্রম করুন!*"

    await update.message.reply_text(msg, parse_mode='Markdown')
