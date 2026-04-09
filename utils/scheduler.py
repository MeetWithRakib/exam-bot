import logging
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from database.db import get_pending_exams, update_exam_status, get_exam
from utils.exam_runner import start_exam, end_exam

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Dhaka")

async def setup_scheduler(application):
    """Initialize scheduler and reschedule any pending exams"""
    scheduler.start()
    logger.info("Scheduler started")

    # Reschedule any pending exams from DB (in case bot restarted)
    pending = get_pending_exams()
    for exam in pending:
        scheduled_at = datetime.fromisoformat(str(exam['scheduled_at']))
        if scheduled_at > datetime.now():
            schedule_exam_job(application, exam['id'], scheduled_at, exam['duration_minutes'])
            logger.info(f"Rescheduled exam {exam['id']} for {scheduled_at}")
        else:
            # Missed exam, mark as cancelled
            update_exam_status(exam['id'], 'cancelled')

def schedule_exam_job(application, exam_id, run_time, duration_minutes=10):
    """Schedule an exam to start at a specific time"""
    job_id = f"exam_start_{exam_id}"
    end_job_id = f"exam_end_{exam_id}"

    # Schedule exam start
    scheduler.add_job(
        start_exam,
        trigger=DateTrigger(run_date=run_time),
        args=[application, exam_id],
        id=job_id,
        replace_existing=True
    )

    # Schedule exam end
    end_time = run_time + timedelta(minutes=duration_minutes)
    scheduler.add_job(
        end_exam,
        trigger=DateTrigger(run_date=end_time),
        args=[application, exam_id],
        id=end_job_id,
        replace_existing=True
    )

    logger.info(f"Exam {exam_id} scheduled: start={run_time}, end={end_time}")

def cancel_exam_jobs(exam_id):
    """Cancel scheduled jobs for an exam"""
    for job_id in [f"exam_start_{exam_id}", f"exam_end_{exam_id}"]:
        try:
            scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id}")
        except Exception:
            pass
