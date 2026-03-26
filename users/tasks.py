from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found, skipping email")
        return
    
    try:
        send_mail(
            subject="Welcome to OlaTech Food 🍔",
            message=f"Hi {user.username},\n\nWelcome to OlaTech Food! We're excited to have you.\n\nStart exploring our menu and place your first order today.\n\nOlaTech Food",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )
        logger.info(f"Welcome email sent to {user.email}")
    
    except Exception as exc:
        logger.error(f"Failed to send welcome email to user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)