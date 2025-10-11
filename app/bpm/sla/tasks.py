import logging
from datetime import datetime

from app.bpm.bpm_schema import CaseStatusEnum
from app.bpm.models import SLA, Case
from app.bpm.utils import escalate_cases
from app.core.db import SessionLocal
from celery import Celery
from sqlalchemy.exc import IntegrityError

app = Celery('tasks', broker='redis://localhost:6379/10')


@app.task
def process_case_sla():
    try:
        db = SessionLocal()
        escalate_cases(db)
        db.commit()
    finally:
        db.close()
