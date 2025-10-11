### app/periodic_reports/celery_config.py

# Standard library imports
from datetime import timedelta

# Third party imports
from celery import Celery
from celery.schedules import crontab

# Local imports
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Create Celery app
celery_app = Celery('bat_reports')

# Celery configuration
celery_app.conf.update(
    broker_url=f'redis://{settings.redis_username}:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}/0',
    result_backend=f'redis://{settings.redis_username}:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    include=['app.periodic_reports.tasks'],
    
    # Beat schedule for periodic tasks
    beat_schedule={
        # Check for scheduled reports every 15 minutes
        'check-scheduled-reports': {
            'task': 'app.periodic_reports.tasks.generate_scheduled_reports_task',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
        },
        
        # Daily cleanup of old report files (runs at 2 AM)
        'cleanup-old-reports': {
            'task': 'app.periodic_reports.tasks.cleanup_old_reports_task',
            'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        
        # Weekly report summary (runs on Mondays at 8 AM)
        'weekly-report-summary': {
            'task': 'app.periodic_reports.tasks.send_weekly_summary_task',
            'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday at 8 AM
        },
    },
    
    # Task routing
    task_routes={
        'app.periodic_reports.tasks.*': {'queue': 'reports'},
    },
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
)
