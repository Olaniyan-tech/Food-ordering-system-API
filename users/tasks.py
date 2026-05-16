from celery import shared_task
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from django.contrib.auth.models import User
from django.conf import settings
from food.constants import BREVO_SENDER
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
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = settings.BREVO_API_KEY
        configuration.host = settings.BREVO_CONFIG_URL

        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
    
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": user.email, "name": user.username}],
            sender=BREVO_SENDER,
            subject="Welcome to BiteBoard 🍔",
            html_content=f"""
                <h2>Hi {user.username},</h2>
                <p>Welcome to BiteBoard! We're excited to have you.</p>
                <p>Start exploring our menu and place your first order today.</p>
                <p>BiteBoard Team</p>
            """
        )

        api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Welcome email sent to {user.email}")
    
    except ApiException as exc:
        logger.error(f"Failed to send welcome email to user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)