from celery import shared_task
from food.selectors import(
    get_order_by_id_for_email, 
    get_vendor_subscription,
    get_vendor_subscription_by_id_for_email,
)
from food.utils import get_valid_vendor_for_email
from food.constants import BREVO_SENDER
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from food.models import Vendor, Order, Plan, Subscription
from django.conf import settings
from datetime import timedelta
from django.utils import timezone
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


def _get_brevo_api():
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = settings.BREVO_API_KEY
    return sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )


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
            logger.warning(f"Unknown order event: {new_status}")
            return
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": order.user.email, "name": order.user.username}],
            sender=BREVO_SENDER,
            subject=email_data["subject"],
            html_content=f"""
                <h2>Hi {order.user.username},</h2>
                <p>{email_data['message']}</p>
                <p>Order Total: ₦{order.total}</p>
                <p>Thank you for choosing BiteBoard</p>
                <p><strong>BiteBoard Team</strong></p>
            """
        )

        _get_brevo_api().send_transac_email(send_smtp_email)
        logger.info(f"Status email sent to {order.user.email} for order {order.id} → {new_status}")

    except ApiException as exc:
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
            html_content = f"""
                <h2>Hi {order.user.username},</h2>
                <p>Your payment of ₦{order.total} has been received successfully.</p>
                <p>Payment Reference: <strong>{order.payment_reference}</strong></p>
                <p>Thank you for choosing BiteBoard</p>
                <p><strong>BiteBoard Team</strong></p>
            """

        else:
            subject = "Payment failed ❌"
            html_content = f"""
                <h2>Hi {order.user.username},</h2>
                <p>Unfortunately your payment for Order {order.payment_reference} failed.</p>
                <p>Please try again or contact support.</p>
                <p>BiteBoard Team</p>
            """
        
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(            
            to=[{"email": order.user.email, "name": order.user.username}],
            sender=BREVO_SENDER,
            subject=subject,
            html_content=html_content
        )

        _get_brevo_api().send_transac_email(send_smtp_email)
        logger.info(f"Payment email sent to {order.user.email} — {payment_status}")
    
    except ApiException as exc:
        logger.error(f"Failed to send payment email for order {order_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)



@shared_task(bind=True, max_retries=3)
def send_subscription_email(self, vendor_id, event):
    try:
        vendor = get_vendor_subscription_by_id_for_email(vendor_id)
    except Vendor.DoesNotExist:
        logger.error(f"Vendor {vendor_id} not found, skipping email")
        return

    try:
        subscription = get_vendor_subscription(vendor)
        plan_name = subscription.plan.name if subscription else "FREE"

        messages = {
            "SUBSCRIBED": {
                "subject": "Subscription activated ✅",
                "message": f"Your {plan_name} plan is now active."
            },
            "EXPIRED": {
                "subject": "Subscription expired ❌",
                "message": "Your subscription has expired. Upgrade to continue enjoying premium features."
            },
            "CANCELLED": {
                "subject": "Subscription cancelled ❌",
                "message": "Your subscription has been cancelled. You are now on the FREE plan."
            },
            "EXPIRING_SOON": {
                "subject": "Subscription expiring soon ⚠️",
                "message": "Your subscription expires in 3 days. Renew to avoid losing access."
            }
        }

        email_data = messages.get(event)
        if not email_data:
            logger.warning(f"Unknown subscription event: {event}")
            return

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": vendor.user.email, "name": vendor.user.username}],
            sender=BREVO_SENDER,
            subject=email_data["subject"],
            html_content=f"""
                <h2>Hi {vendor.business_name},</h2>
                <p>{email_data['message']}</p>
                <p>Thank you for using BiteBoard.</p>
                <p><strong>BiteBoard Team</strong></p>
            """
        )

        _get_brevo_api().send_transac_email(send_smtp_email)
        logger.info(f"Subscription email sent to {vendor.user.email} - {event}")
        
    except ApiException as exc:
        logger.error(f"Failed to send subscription email for vendor {vendor_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def check_expired_subscriptions():
    from food.services.subscription_service import record_subscription_history
    # Runs every midnight — auto expires subscriptions.

    free_plan = Plan.objects.get(name="FREE")
    expired = Subscription.objects.filter(
        status="ACTIVE",
        end_date__lt=timezone.now(),
    ).exclude(plan=free_plan).select_related("vendor")


    count = 0
    for subscription in expired:
        subscription.status = "EXPIRED"
        subscription.plan = free_plan
        subscription.save(update_fields=["status", "plan", "updated_at"])
        record_subscription_history(subscription.vendor, free_plan, "EXPIRED")
        send_subscription_email.delay(subscription.vendor.id, "EXPIRED")
        count += 1

    logger.info(f"Expired {count} subscriptions")


@shared_task
def notify_expiring_subscriptions():
    # Runs every day at 9am — warns vendors 3 days before expiry.

    expiring_soon = Subscription.objects.filter(
        status="ACTIVE",
        end_date__lte=timezone.now() + timedelta(days=3),
        end_date__gt=timezone.now()
    ).exclude(plan__name="FREE").select_related("vendor")

    count = 0
    for subscription in expiring_soon:
        send_subscription_email.delay(subscription.vendor.id, "EXPIRING_SOON")
        count += 1
    
    logger.info(f"Notified {count} vendors of expiring subscriptions")
    

VENDOR_EMAIL_MESSAGES = {
    "APPROVED": {
        "subject": "Your vendor application has been approved 🎉",
        "html": lambda vendor: f"""
            <h2>Hi {vendor.user.username},</h2>
            <p>Congratulations! Your vendor application for 
            <strong>{vendor.business_name}</strong> has been approved.</p>
            <p>You can now log in to your dashboard to:</p>
            <ul>
                <li>Add your food items</li>
                <li>Manage your menu</li>
                <li>Start receiving orders</li>
            </ul>
            <p>Welcome to BiteBoard!</p>
            <p><strong>BiteBoard Team</strong></p>
        """
    },

    "REJECTED": {
        "subject": "You vendor application has been rejected ❌",
        "html": lambda vendor: f"""
            <h2>Hi {vendor.user.username},</h2>
            <p>Thank you for applying to become a vendor on BiteBoard.</p>
            <p>Unfortunately, your application for 
            <strong>{vendor.business_name}</strong> 
            has not been approved at this time.</p>
            <p>This may be due to:</p>
            <ul>
                <li>Incomplete business information</li>
                <li>Business name already in use</li>
                <li>Location not currently supported</li>
            </ul>
            <p>You are welcome to reapply with updated information 
            or contact our support team for more details.</p>
            <p><strong>BiteBoard Team</strong></p>
        """
    },

    "DEACTIVATED": {
        "subject": "Your vendor account has been deactivated ⚠️",
        "html": lambda vendor: f"""
            <h2>Hi {vendor.user.username},</h2>
            <p>Your vendor account for 
            <strong>{vendor.business_name}</strong> 
            has been temporarily deactivated.</p>
            <p>This means:</p>
            <ul>
                <li>Your foods are no longer visible to customers</li>
                <li>You cannot receive new orders</li>
                <li>Your dashboard access is suspended</li>
            </ul>
            <p>If you believe this is a mistake or would like 
            to resolve this, please contact our support team.</p>
            <p><strong>BiteBoard Team</strong></p>
        """
    },

    "ACTIVATED": {
        "subject": "Your vendor account has been reactivated ✅",
        "html": lambda vendor: f"""
            <h2>Hi {vendor.user.username},</h2>
            <p>Great news! Your vendor account for 
            <strong>{vendor.business_name}</strong> 
            has been reactivated.</p>
            <p>You can now:</p>
            <ul>
                <li>Access your vendor dashboard</li>
                <li>Manage your menu</li>
                <li>Start receiving orders again</li>
            </ul>
            <p>Welcome back to BiteBoard Food!</p>
            <p><strong>BiteBoard Team</strong></p>
        """
    },   
}


def _send_vendor_email(vendor, email_type):
    email_data = VENDOR_EMAIL_MESSAGES.get(email_type)
    if not email_data:
        logger.warning(f"No email template for vendor email type: {email_type}")
        return
    
    api_instance = _get_brevo_api()

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": vendor.user.email, "name": vendor.user.username}],
        sender=BREVO_SENDER,
        subject=email_data["subject"],
        html_content=email_data["html"](vendor)
    )

    api_instance.send_transac_email(send_smtp_email)
    

@shared_task(bind=True, max_retries=3)
def send_vendor_status_email(self, email_type, vendor_id):
    vendor = get_valid_vendor_for_email(vendor_id)
    if not vendor:
        return

    try:
        _send_vendor_email(vendor, email_type)
        logger.info(
            f"{email_type} email sent to {vendor.user.email} "
            f"for vendor: {vendor.business_name}"
        )

    except ApiException as exc:
        logger.error(
            f"Failed to send {email_type} email for vendor {vendor_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_vendor_subscription_payment_email(self, vendor_id, plan_name, reference):
    try:
        vendor = get_vendor_subscription_by_id_for_email(vendor_id)
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor {vendor_id} not found, skipping subscription payment email")
        return
    
    if not vendor.user: 
        logger.critical(f"Vendor {vendor_id} exists but has no user attached.")
        return

    if not plan_name:
        plan_name = "Unknown Plan"

    try:
        subject = "Subscription payment successful ✅"
        html_content = f"""
        <h2>Hi {vendor.user.username},</h2>
        <p>Your payment for the {plan_name} plan has been received successfully.</p>
        <p>Payment Reference: <strong>{reference}</strong></p>
        <p>Thank you for subscribing to BiteBoard!</p>
        <p><strong>BiteBoard Team</strong></p>
    """
        
        api_instance = _get_brevo_api()
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": vendor.user.email, "name": vendor.user.username}],
            sender=BREVO_SENDER,
            subject=subject,
            html_content=html_content
        )

        api_instance.send_transac_email(send_smtp_email)
        logger.info(
            f"Subscription payment email sent to {vendor.user.email} "
            f"for plan: {plan_name}"
        )
    
    except ApiException as exc:
        logger.error(
            f"Failed to send subscription payment email for vendor {vendor_id}: {exc}"
        )
        raise self.retry(exc=exc, countdown=60)



