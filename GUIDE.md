# 📚 Telegram পরীক্ষা বট — সম্পূর্ণ গাইড

## ফিচার সমূহ
- ✅ AI দিয়ে স্বয়ংক্রিয় MCQ ও লিখিত প্রশ্ন তৈরি
- ✅ নির্দিষ্ট সময়ে গ্রুপে পরীক্ষা পোস্ট
- ✅ তাৎক্ষণিক উত্তর যাচাই ও ফলাফল
- ✅ প্রতি সদস্যের অংশগ্রহণ ও সঠিক উত্তরের হার
- ✅ পরীক্ষাভিত্তিক / সাপ্তাহিক / মাসিক / সর্বকালীন লিডারবোর্ড

---

## ধাপ ১: GitHub-এ কোড আপলোড করুন

1. [github.com](https://github.com) এ যান → নতুন অ্যাকাউন্ট বা লগইন
2. "New Repository" ক্লিক করুন
3. Repository নাম: `exam-bot`
4. Public রাখুন → "Create repository"
5. সব ফাইল আপলোড করুন (drag & drop করা যাবে)

---

## ধাপ ২: Zeabur-এ Deploy করুন

1. [zeabur.com](https://zeabur.com) এ লগইন করুন
2. Dashboard থেকে **"New Project"** ক্লিক করুন
3. **"Deploy from GitHub"** সিলেক্ট করুন
4. `exam-bot` repository সিলেক্ট করুন
5. Deploy হবে — একটু সময় লাগবে

---

## ধাপ ৩: Environment Variables সেট করুন

Zeabur Dashboard → আপনার সার্ভিস → **"Variables"** ট্যাব:

| Variable Name | মান |
|--------------|-----|
| `TELEGRAM_BOT_TOKEN` | আপনার নতুন Bot Token |
| `GEMINI_API_KEY` | আপনার Gemini API Key |
| `ADMIN_IDS` | আপনার Telegram User ID (কমা দিয়ে একাধিক) |

### আপনার Telegram User ID কীভাবে পাবেন?
- [@userinfobot](https://t.me/userinfobot) এ মেসেজ করুন
- সে আপনার ID জানিয়ে দেবে

---

## ধাপ ৪: বটকে গ্রুপে যোগ করুন

1. আপনার Telegram গ্রুপে যান
2. Group Info → Add Member → আপনার বটের নাম সার্চ করুন
3. বটকে **Admin** করুন (মেসেজ পাঠানোর permission দিন)

---

## বট ব্যবহার করার পদ্ধতি

### প্রথমে Admin হিসেবে বটে মেসেজ করুন:
```
/start
```

### টপিক যোগ করুন:
```
/addtopic
```
বট আপনাকে শিরোনাম ও বিষয়বস্তু চাইবে।

**অথবা সরাসরি কন্টেন্ট পেস্ট করুন** — AI নিজেই প্রশ্ন তৈরি করবে।

### পরীক্ষা শিডিউল করুন:
```
/schedule <topic_id> <type> <date> <time> <duration> <questions>
```

উদাহরণ:
```
/schedule 1 mcq 2024-01-15 14:30 10 5
```
এর মানে: Topic 1 থেকে MCQ পরীক্ষা, ১৫ জানুয়ারি দুপুর ২:৩০ তে, ১০ মিনিট, ৫টি প্রশ্ন

লিখিত পরীক্ষা:
```
/schedule 1 written 2024-01-15 14:30 15 3
```

### লিডারবোর্ড দেখুন:
```
/leaderboard          → সর্বকালীন
/leaderboard weekly   → সাপ্তাহিক
/leaderboard monthly  → মাসিক
```

### আপনার স্ট্যাটস:
```
/mystats
```

---

## সদস্যরা কীভাবে উত্তর দেবেন

**MCQ পরীক্ষায়:**
- প্রশ্নের নিচে A, B, C, D বাটন আসবে
- ক্লিক করলেই তাৎক্ষণিক ফলাফল দেখাবে

**লিখিত পরীক্ষায়:**
- গ্রুপে টাইপ করুন: `Q1: আপনার উত্তর`
- AI উত্তর যাচাই করে ফলাফল দেবে

---

## সমস্যা হলে

- বট কাজ না করলে: Zeabur Dashboard → Logs দেখুন
- পরীক্ষা বাতিল করতে: `/cancelexam`
- সব পেন্ডিং পরীক্ষা দেখতে: `/cancelexam` (ID ছাড়া)
