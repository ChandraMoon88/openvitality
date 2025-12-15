# src/core/task_scheduler.py
"""
Manages background and delayed tasks like sending reminders or follow-ups,
using APScheduler with a persistent job store.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
# from pytz import utc

# from . import config, logger

class TaskScheduler:
    def __init__(self, db_url: str):
        """
        Initializes the TaskScheduler.
        
        Args:
            db_url: The database URL for the persistent job store.
        """
        # jobstores = {
        #     'default': SQLAlchemyJobStore(url=db_url)
        # }
        # executors = {
        #     'default': {'type': 'threadpool', 'max_workers': 10},
        # }
        # self.scheduler = AsyncIOScheduler(
        #     jobstores=jobstores,
        #     executors=executors,
        #     timezone=utc
        # )
        # logger.info("TaskScheduler initialized with SQLAlchemy job store.")
        print("TaskScheduler initialized.")

    def start(self):
        """Starts the scheduler."""
        # self.scheduler.start()
        # logger.info("Task scheduler started.")
        print("Task scheduler started.")


    def stop(self):
        """Stops the scheduler gracefully."""
        # self.scheduler.shutdown()
        # logger.info("Task scheduler stopped.")
        print("Task scheduler stopped.")


    def add_job(self, func, *args, **kwargs):
        """
        Adds a job to the scheduler.
        
        `func` can be a function path string (e.g., 'my_module.my_function')
        or a callable. Other arguments are passed to APScheduler's `add_job`.
        
        Example:
        scheduler.add_job(
            'src.tasks.send_reminder', 
            trigger='date', 
            run_date='2025-12-25 10:00:00', 
            args=['user123', 'Take your medication.']
        )
        """
        # return self.scheduler.add_job(func, *args, **kwargs)
        print(f"Adding job {func} to scheduler.")

    def cancel_job(self, job_id: str):
        """Removes a job from the scheduler."""
        # try:
        #     self.scheduler.remove_job(job_id)
        #     logger.info(f"Cancelled job {job_id}.")
        # except JobLookupError:
        #     logger.warning(f"Could not find job {job_id} to cancel.")
        print(f"Cancelling job {job_id}.")

# --- Example task functions (these would live in a separate `src/tasks.py` file) ---

def send_medication_reminder(user_id: str, message: str):
    """
    A task function that would send a medication reminder to a user.
    """
    # Logic to connect to a notification service (SMS, Push, etc.)
    print(f"SENDING REMINDER to {user_id}: {message}")

def run_daily_data_aggregation():
    """
    A task to perform daily data processing.
    """
    print("RUNNING daily data aggregation task.")

# --- Initialization ---
# This would typically be done in the main application setup
# scheduler = TaskScheduler(db_url=config.database.db_url)
#
# In main.py:
# @app.on_event("startup")
# async def startup_event():
#     scheduler.start()
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     scheduler.stop()
