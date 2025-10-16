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
    # Fetch and import CURB trips every 24 hours at 2 AM
    "curb-fetch-and-import": {
        "task": "app.curb.tasks.fetch_and_import_curb_trips",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM UTC
        "options": {
            "timezone": "America/New_York"
        }
    },
    
    # Reconcile CURB trips every 24 hours at 3 AM
    "curb-reconcile": {
        "task": "app.curb.tasks.reconcile_curb_trips",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM UTC
        "options": {
            "timezone": "America/New_York"
        }
    },
    
    # Post CURB trips to ledger every 24 hours at 4 AM
    "curb-post": {
        "task": "app.curb.tasks.post_curb_trips",
        "schedule": crontab(hour=4, minute=0),  # Daily at 4 AM UTC
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
}

# Worker configuration
worker_hijack_root_logger = False
worker_log_color = False