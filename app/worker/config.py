### app/worker/config.py

"""
Celery configuration settings

This file contains all the Celery configurations including:
- Broker and result backend settings
- Task serialization settings
- Timezone configuration
- Beat schedule for periodic tasks
"""

# Third party imports
from celery.schedules import crontab

# Local imports
from app.core.config import settings

# Broker and result backend configurations
broker_url = f"redis://{settings.redis_host}:{settings.redis_port}/0"
result_backend = f"redis://{settings.redis_host}:{settings.redis_port}/0"

# Task serialization
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "UTC"
enable_utc = True

# Task settings
task_track_started = True
task_time_limit = 30 * 60 # 30 minutes
task_soft_time_limit = 25 * 60 # 25 minutes
worker_prefetch_multiplier = 1
task_acks_late = True
worker_disable_rate_limits = False


# Beat schedule configuration
# This defines when periodic tasks should run
beat_schedule = {
    # CURB trip processing - run every 24 hours at 2 AM UTC
    "curb-trip-processing": {
        "task": "app.curb.tasks.fetch_and_reconcile_curb_trips",
        "schedule": crontab(hour=6, minute=0),  # Run daily at 6 AM UTC
        "options": {
            "timezone": "America/New_York"
        }
    },
    "curb-trip-reconciliation": {
        "task": "app.curb.tasks.reconcile_curb_trips_only",
        "schedule": crontab(hour=7, minute=0),  # Run daily at 7 AM UTC
        "options": {
            "timezone": "America/New_York"
        }
    },
    "curb-trip-posting": {
        "task": "app.curb.tasks.post_curb_trips_only",
        "schedule": crontab(hour=8, minute=0),  # Run daily at 8 AM UTC
        "options": {
            "timezone": "America/New_York"
        }
    },
    "generate-weekly-dtrs": {
        "task": "app.ledger.tasks.generate_weekly_dtrs",
        "schedule": crontab(hour=5, minute=0, day_of_week="sun"), # Run every Sunday at 5 AM UTC
        "options": {
            "timezone": "America/New_York"
        }
    },
    
    # Periodic reports tasks
    "scheduled-reports": {
        "task": "app.periodic_reports.tasks.scheduled_reports_task",
        "schedule": crontab(minute="*/15"),  # Check every 15 minutes for scheduled reports
        "options": {
            "timezone": "UTC"
        }
    },
    "cleanup-old-reports": {
        "task": "app.periodic_reports.tasks.cleanup_old_reports_task",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM UTC
        "options": {
            "timezone": "UTC"
        }
    },
    "weekly-summary": {
        "task": "app.periodic_reports.tasks.send_weekly_summary_task",
        "schedule": crontab(hour=9, minute=0, day_of_week="mon"),  # Weekly on Monday at 9 AM UTC
        "options": {
            "timezone": "UTC"
        }
    },
    
    # Sample task schedule
    # "sample-task": {
    #     "task": "app.worker.tasks.sample_task",
    #     "schedule": crontab(minute="*/1"), # Run every minute
    #     "args": (16, 16)
    # }
}

# Worker configuration
worker_hijack_root_logger = False
worker_log_color = False