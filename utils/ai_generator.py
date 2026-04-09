import google.generativeai as genai
import json
import os
import re
import logging

logger = logging.getLogger(__name__)

def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set!")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-1.5-flash')

def generate_mcq_questions(content, num_questions=5):
    """Generate MCQ questions from content using Gemini AI"""
    model = setup_gemini()

    prompt = f"""
তুমি একজন পরীক্ষা প্রশ্ন তৈরিকারী। নিচের বিষয়বস্তু থেকে {num_questions}টি MCQ প্রশ্ন তৈরি করো।

বিষয়বস্তু:
{content}

নিয়ম:
- প্রতিটি প্রশ্নে ৪টি অপশন থাকবে (A, B, C, D)
- একটিই সঠিক উত্তর
- প্রশ্ন বাংলায় বা ইংরেজিতে হতে পারে (বিষয়বস্তু অনুযায়ী)
- প্রতিটি সঠিক উত্তরে ১০ পয়েন্ট

শুধুমাত্র JSON ফরম্যাটে উত্তর দাও, অন্য কিছু লিখবে না:
{{
  "questions": [
    {{
      "id": 1,
      "question": "প্রশ্ন এখানে",
      "options": {{
        "A": "অপশন A",
        "B": "অপশন B",
        "C": "অপশন C",
        "D": "অপশন D"
      }},
      "correct_answer": "A",
      "explanation": "সঠিক উত্তরের ব্যাখ্যা"
    }}
  ]
}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Remove markdown code blocks if present
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        data = json.loads(text)
        return data.get("questions", [])
    except Exception as e:
        logger.error(f"Error generating MCQ: {e}")
        return []

def generate_written_questions(content, num_questions=3):
    """Generate written/short-answer questions from content"""
    model = setup_gemini()

    prompt = f"""
তুমি একজন পরীক্ষা প্রশ্ন তৈরিকারী। নিচের বিষয়বস্তু থেকে {num_questions}টি সংক্ষিপ্ত প্রশ্ন তৈরি করো।

বিষয়বস্তু:
{content}

নিয়ম:
- প্রশ্নের উত্তর ১-৩ বাক্যে দেওয়া যাবে
- প্রতিটি উত্তরের কিওয়ার্ড/মূল পয়েন্ট থাকবে
- প্রশ্ন বাংলায় বা ইংরেজিতে হতে পারে (বিষয়বস্তু অনুযায়ী)

শুধুমাত্র JSON ফরম্যাটে উত্তর দাও, অন্য কিছু লিখবে না:
{{
  "questions": [
    {{
      "id": 1,
      "question": "প্রশ্ন এখানে",
      "model_answer": "আদর্শ উত্তর",
      "keywords": ["কীওয়ার্ড১", "কীওয়ার্ড২", "কীওয়ার্ড৩"],
      "points": 20
    }}
  ]
}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        data = json.loads(text)
        return data.get("questions", [])
    except Exception as e:
        logger.error(f"Error generating written questions: {e}")
        return []

def evaluate_written_answer(question, model_answer, keywords, user_answer):
    """Use AI to evaluate a written answer"""
    model = setup_gemini()

    prompt = f"""
তুমি একজন পরীক্ষক। নিচের প্রশ্নের উত্তর মূল্যায়ন করো।

প্রশ্ন: {question}
আদর্শ উত্তর: {model_answer}
মূল কীওয়ার্ড: {', '.join(keywords)}
শিক্ষার্থীর উত্তর: {user_answer}

মূল্যায়ন করো এবং শুধুমাত্র JSON ফরম্যাটে উত্তর দাও:
{{
  "score_percentage": 0-100,
  "is_correct": true/false,
  "feedback": "সংক্ষিপ্ত মন্তব্য (বাংলায়)"
}}

বিবেচনা করো:
- উত্তরে মূল কীওয়ার্ড আছে কিনা
- উত্তর মূলত সঠিক কিনা
- আংশিক সঠিক হলে আনুপাতিক নম্বর দাও
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        data = json.loads(text)
        return data
    except Exception as e:
        logger.error(f"Error evaluating answer: {e}")
        return {"score_percentage": 0, "is_correct": False, "feedback": "মূল্যায়ন করা সম্ভব হয়নি"}
