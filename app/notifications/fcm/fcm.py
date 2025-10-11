### app/notifications/fcm/fcm.py

from firebase_admin import messaging
from app.utils.logger import get_logger

logger = get_logger(__name__)

def send_fcm_notification_to_topic(topic: str, title: str, body: str):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        topic=topic,
    )

    try:
        response = messaging.send(message)
        logger.info("Successfully sent FCM notification: %s", response)
        return response
    except Exception as e:
        logger.error("Failed to send FCM notification: %s", e)
        return None
