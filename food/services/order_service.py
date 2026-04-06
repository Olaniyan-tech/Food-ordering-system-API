from django.db import transaction
from django.utils import timezone
from food.models import Food, Order, OrderStatusHistory
from food.tasks import send_order_status_email, send_payment_email
from django.core.exceptions import ValidationError
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


STATUS_TIMESTAMP_FIELDS = {
    "PENDING": None,
    "CONFIRMED": "confirmed_at",
    "PREPARING": "preparing_at",
    "READY": "ready_at",
    "OUT FOR DELIVERY": "out_for_delivery_at",
    "DELIVERED": "delivered_at",
    "CANCELLED": "cancelled_at",
}


def _require_status(order, expected_status, message):
    if order.status != expected_status:
        raise ValidationError(message)


@transaction.atomic
def update_order_status(order, new_status, changed_by=None):
    if order.status == new_status:
        raise ValidationError(f"Order is already {new_status}")

    if new_status not in STATUS_TIMESTAMP_FIELDS:
        raise ValidationError("Invalid order status")
    
    order.status = new_status
    timestamp_field = STATUS_TIMESTAMP_FIELDS.get(new_status)

    if timestamp_field:
        setattr(order, timestamp_field, timezone.now())
    else:
        logger.warning(f"No timestamp field for status {new_status}")
    
    update_fields = ["status", "updated_at"]
    if timestamp_field:
        update_fields.append(timestamp_field)

    order.save(update_fields=update_fields)

    if changed_by:
        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
            changed_by=changed_by
        )

    transaction.on_commit(lambda: send_order_status_email.delay(order.id, new_status))
    transaction.on_commit(lambda: cache.delete(f"vendor_dashboard_stats_{order.vendor_id}"))

    return order


@transaction.atomic
def finalize_order(order, user=None):
    if order.status != "PENDING":
        raise ValidationError("Only pending order can be finalized")
    
    if not order.items.exists():
        raise ValidationError("Cannot checkout an empty cart")
    
    for item in order.items.select_related("food"):
        food = Food.objects.select_for_update().get(id=item.food_id)
        if food.stock < item.quantity:
            raise ValidationError(f"{food.name} is out of stock")
        food.stock -= item.quantity
        food.save(update_fields=["stock", "updated_at"])
        
    return update_order_status(order, "CONFIRMED", changed_by=user)


@transaction.atomic
def mark_preparing(order, user=None):
    _require_status(order, "CONFIRMED", "Order must be confirmed before preparing")
    
    return update_order_status(order, "PREPARING", changed_by=user)


@transaction.atomic
def mark_ready(order, user=None):
    _require_status(order, "PREPARING", "Order must be preparing before ready")
    
    return update_order_status(order, "READY", changed_by=user)


@transaction.atomic
def cancel_order(order, user=None):
    if order.status not in ["PENDING", "CONFIRMED"]:
        raise ValidationError("Order is already being prepared or delivered and cannot be cancelled.")
    
    if order.status == "CONFIRMED":
        for item in order.items.select_related("food"):
            food = Food.objects.select_for_update().get(id=item.food_id)
            item.food.stock += item.quantity
            item.food.save(update_fields=["stock", "updated_at"])

    return update_order_status(order, "CANCELLED", changed_by=user)


@transaction.atomic
def mark_out_for_delivery(order, user=None):
    _require_status(
        order,
        "READY",
        "Order must be ready before marking as out for delivery",
    )
    
    return update_order_status(order, "OUT FOR DELIVERY", changed_by=user)


@transaction.atomic
def mark_delivered(order, user=None):
    _require_status(order, "OUT FOR DELIVERY", "Order must be out for delivery")
    
    return update_order_status(order, "DELIVERED", changed_by=user)


@transaction.atomic
def update_payment_status(order, status):
    order = Order.objects.select_for_update().get(id=order.id)
                                                  
    if order.payment_status == status:
        return
    order.payment_status = status
    order.save(update_fields=["payment_status", "updated_at"])

    transaction.on_commit(lambda: send_payment_email.delay(order.id, status))


ADMIN_TRANSITION_MAP = {
    "PREPARING": mark_preparing,
    "READY": mark_ready,
    "OUT FOR DELIVERY": mark_out_for_delivery,
    "DELIVERED": mark_delivered,
    "CANCELLED": cancel_order,
}


VENDOR_TRANSITION_MAP = {
    "PREPARING": mark_preparing,
    "READY": mark_ready,
    "CANCELLED": cancel_order,
}

