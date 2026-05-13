from django.db import transaction
from django.utils import timezone
from food.models import Food, Order, OrderStatusHistory
from food.services.subscription_service import get_or_create_free_subscription, check_vendor_order_limit
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
    
    items = list(order.items.select_related("food__vendor__subscription__plan"))
    for item in items:
        food = Food.objects.select_for_update().get(id=item.food_id)
        
        vendor = food.vendor
        subscription = get_or_create_free_subscription(vendor)
        if not subscription.is_valid():
            raise ValidationError(
                f"{vendor.business_name} is currently unavailable. "
                f"Please remove their items from your cart"
            )
        
        if food.stock < item.quantity:
            raise ValidationError(f"{food.name} is out of stock")
        
        try:
            check_vendor_order_limit(food.vendor)
        except ValidationError:
            raise ValidationError(
                f"{food.vendor.business_name} cannot receive more orders this month."
            )

        food.stock -= item.quantity
        food.save(update_fields=["stock", "updated_at"])
    
    vendors = set(item.food.vendor for item in items)

    has_delivery_fee = any(
        vendor.subscription.plan.delivery_fee
        for vendor in vendors
    )
    
    if has_delivery_fee:
        order.delivery_fee = 0
    else:
        order.delivery_fee = 500.00 # default delivery fee ₦500
    
    order.total = sum(item.subtotal for item in order.items.all()) + order.delivery_fee
    order.save(update_fields=["total", "delivery_fee", "updated_at"])
        
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
            food.stock += item.quantity
            food.save(update_fields=["stock", "updated_at"])

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

