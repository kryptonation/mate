from io import StringIO

import boto3
from celery import shared_task

from app.core.db import get_db
from app.utils.logger import get_logger
from app.core.config import settings
from app.utils.s3_utils import s3_utils
from app.ezpass.services import ezpass_service
from app.ezpass.utils import validate_ezpass_file

logger = get_logger(__name__)

# A mock class to make the S3 file compatible with the existing validator
class MockUploadFile:
    def __init__(self, content: bytes, filename: str):
        self.file = StringIO(content.decode('utf-8'))
        self.filename = filename

@shared_task(bind=True, name='app.ezpass.tasks.process_report_from_s3')
def process_report_from_s3(self, s3_key: str, import_by: str):
    """
    Celery task to download an EZPass report from S3, process it,
    and then archive the file.
    """
    task_id = self.request.id
    logger.info(f"[Task ID: {task_id}] Starting EZPass report processing from S3 key: {s3_key}")
    db = next(get_db())
    try:
        # 1. Download the file from S3
        file_bytes = s3_utils.download_file(s3_key)
        if not file_bytes:
            raise FileNotFoundError(f"File not found in S3 at key: {s3_key}")

        # 2. Validate and parse the file
        mock_file = MockUploadFile(content=file_bytes, filename=s3_key.split('/')[-1])
        validated_rows = validate_ezpass_file(mock_file)
        
        # 3. Process the data (import, associate, post)
        result = ezpass_service.process_ezpass_data(db, validated_rows)
        
        # 4. (Optional but recommended) Move processed file to an archive location
        archive_key = s3_key.replace('incoming/', 'processed/')
        s3_client = boto3.client('s3')
        s3_client.copy_object(Bucket=settings.s3_bucket_name, CopySource={'Bucket': settings.s3_bucket_name, 'Key': s3_key}, Key=archive_key)
        s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=s3_key)
        
        logger.info(f"[Task ID: {task_id}] Successfully processed and archived S3 file {s3_key}")
        return result

    except Exception as e:
        logger.error(f"[Task ID: {task_id}] Failed to process S3 file {s3_key}: {e}", exc_info=True)
        # Optional: Move to a 'failed' prefix in S3
        # s3_utils.copy_object(...) and s3_utils.delete_object(...)
        raise
    finally:
        db.close()