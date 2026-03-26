from celery import shared_task
from django.core.mail import send_mail
from food.selectors import get_order_by_id_for_email
from food.models import Order
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

STATUS_EMAIL_MESSAGES = {
    "CONFIRMED" : {
        "subject": "Your order has been confirmed ✅",
        "message": "Your order has been confirmed and will soon start preparing.",
    },

    "PREPARING" : {
        "subject": "Your order is being prepared 🍳",
        "message": "Great news! The kitchen has started preparing your order. Sit tight!",
    },

    "READY": {
        "subject": "Your order is ready 🎉",
        "message": "Your order is ready and waiting for pickup by your delivery driver.",
    },

    "OUT FOR DELIVERY": {
        "subject": "Your order is on the way 🛵",
        "message": "The rider has picked up your order and is heading your way.",
    },

    "DELIVERED": {
        "subject": "Order delivered - enjoy your meal 🍽",
        "message": "Your order has been delivered. We hope you enjoyed it! Don't forget to leave a review.",
    },

    "CANCELLED": {
        "subject": "Your order has been cancelled ❌",
        "message": "Your order has been cancelled. If you have any questions, please contact us.",
    }

}


@shared_task(bind=True, max_retries=3)
def send_order_status_email(self, order_id, new_status):
    try:
        order = get_order_by_id_for_email(order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found, skipping email")
        return

    try:
        email_data = STATUS_EMAIL_MESSAGES.get(new_status)
        if not email_data:
            return
        
        send_mail(
            subject=email_data["subject"],
            message=f"Hi {order.user.username},\n\n{email_data['message']}\n\nOrder ID: {order.id}\nTotal: ₦{order.total}\n\nThank you for choosing OlaTech Food!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False
        )

        logger.info(f"Status email sent to {order.user.email} for order {order.id} → {new_status}")

    except Exception as exc:
        logger.error(f"Failed to send status email for order {order.id}: {exc} ")
        raise self.retry(exc=exc, countdown=60)
    

@shared_task(bind=True, max_retries=3)
def send_payment_email(self, order_id, payment_status):
    try:
        order = get_order_by_id_for_email(order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found, skipping email")
        return
    
    try:
        if payment_status == "PAID":
            subject = "Payment successful ✅"
            message = f"Hi {order.user.username},\n\nYour payment of ₦{order.total} has been received successfully.\n\nOrder ID: {order.id}\n\nThank you for choosing OlaTech Food!"
        
        else:
            subject = "Payment failed ❌"
            message = f"Hi {order.user.username},\n\nUnfortunately your payment for Order {order.id} failed.\n\nPlease try again or contact support.\n\nOlaTech Food"
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False
        )

        logger.info(f"Payment email sent to {order.user.email} — {payment_status}")
    
    except Exception as exc:
        logger.error(f"Failed to send payment email for order {order_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)