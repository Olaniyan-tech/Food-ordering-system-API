import requests
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError

def initialize_payment(order):
    if order.payment_status == "PAID":
        raise ValidationError("Order has already been paid for")
    
    if order.status != "CONFIRMED":
        raise ValidationError("Only confirmed orders can be paid for")
    
    if order.total <= 0:
        raise ValidationError("Order total must be greater than 0")

    reference = f"ORDER-{order.id}-{uuid.uuid4().hex[:8].upper()}"

    headers ={
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "email": order.user.email,
        "amount": int(order.total * 100),
        "reference": reference,
        "callback_url": f"{settings.BASE_URL}/api/order/verify/{reference}/", 
        "metadata": {
            "order_id": order.id,
            "user_id": order.user.id,
            "username": order.user.username,
        }
    }

    response = requests.post(
        f"{settings.PAYSTACK_BASE_URL}/transaction/initialize",
        json=payload,
        headers=headers
    )

    if response.status_code != 200:
        print(response.json())
        raise ValidationError("Payment initialization failed. Try again.")
    
    data = response.json()

    if not data.get("status"):
        raise ValidationError(data.get("message", "Payment initialization failed"))
    
    order.payment_reference = reference
    order.payment_status = "PENDING"
    order.save(update_fields=["payment_reference", "payment_status", "updated_at"])

    return data["data"]["authorization_url"], reference

def verify_payment(reference):
    headers ={
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }

    response = requests.get(
        f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}",
        headers=headers
    )

    if response.status_code != 200:
        raise ValidationError("Payment verification failed. Try again.")
    
    data = response.json()

    if not data.get("status"):
        raise ValidationError(data.get("message", "Verification failed."))
    
    return data["data"]
