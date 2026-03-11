from django.db import transaction
from django.utils import timezone
from food.models import Order, OrderStatusHistory
from django.core.exceptions import ValidationError


STATUS_TIMESTAMP_FIELDS = {
    "PENDING": None,
    "CONFIRMED": "confirmed_at",
    "PREPARING": "preparing_at",
    "READY": "ready_at",
    "OUT FOR DELIVERY": "out_for_delivery_at",
    "DELIVERED": "delivered_at",
    "CANCELLED": "cancelled_at",
}


@transaction.atomic
def update_order_status(order, new_status, changed_by=None):
    if order.status == new_status:
        return order

    order.status = new_status
    timestamp_field =STATUS_TIMESTAMP_FIELDS.get(new_status) 

    if timestamp_field:
        setattr(order, timestamp_field, timezone.now())

    update_fields = ["status", "updated"]

    if timestamp_field:
        update_fields.append(timestamp_field)
    order.save(update_fields=update_fields)

    if changed_by:
        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
            changed_by=changed_by
        )

    return order


@transaction.atomic
def finalize_order(order, address=None, phone=None, user=None):
    if order.status != "PENDING":
        raise ValidationError("Only pending order can be finalized")
    
    if not order.items.exists():
        raise ValidationError("Cannot checkout an empty cart")
    
    if address:
        order.address = address    
    if phone:
        order.phone = phone

    order.save(update_fields=["address", "phone", "updated"])

    return update_order_status(order, "CONFIRMED", changed_by=user)


@transaction.atomic
def mark_preparing(order, user=None):
    if order.status != "CONFIRMED":
        raise ValidationError("Order must be confirmed before preparing")
    
    return update_order_status(order, "PREPARING", changed_by=user)


@transaction.atomic
def mark_ready(order, user=None):
    if order.status != "PREPARING":
        raise ValidationError("Order must be preparing before ready")
    
    return update_order_status(order, "READY", changed_by=user)


@transaction.atomic
def cancel_order(order, user=None):
    if order.status not in ["PENDING", "CONFIRMED"]:
        raise ValidationError("Order is already being prepared or delivered and cannot be cancelled.")
    return update_order_status(order, "CANCELLED", changed_by=user)

@transaction.atomic
def mark_out_for_delivery(order, user=None):
    valid_pre_states = ["CONFIRMED", "PREPARING", "READY"]
    if order.status not in valid_pre_states:
        raise ValidationError("Order must be confirmed before delivery")
    return update_order_status(order, "OUT FOR DELIVERY", changed_by=user)

@transaction.atomic
def mark_delivered(order, user=None):
    if order.status != "OUT FOR DELIVERY":
        raise ValidationError("Order must be out for delivery")
    return update_order_status(order, "DELIVERED", changed_by=user)


# @transaction.atomic
# def mark_refunded(order, user=None, reason=None):
#     if order.status not in ["CANCELLED", "DELIVERED"]:
#         raise ValidationError("Only cancelled or delivered orders can be refunded")
    
#     if order.status == "DELIVERED" and not reason:
#         raise ValidationError("Refund after delivery requires a reason")
    
#     return update_order_status(order, "REFUNDED", changed_by=user)