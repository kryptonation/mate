### app/worker/app.py

"""
Main Celery Application Configuration

This file sets up the Celery application instance with Redis as broker and result backend.
It also handles task discovery from multiple modules and configures timezone settings.
"""

# Third party imports
from celery import Celery

# Create Celery Instance
app = Celery("BAT_scheduler")

# Configure celery from separate config file
app.config_from_object("app.worker.config")

# Auto discover tasks from different modules
# This will look for tasks.py files in specified modules/packages
app.autodiscover_tasks([
    "app.worker",
    "app.curb",
    "app.ledger",
])

if __name__ == "__main__":
    app.start()
