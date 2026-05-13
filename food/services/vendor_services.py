from food.models import Vendor, Food, OrderItem
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from food.tasks import send_vendor_status_email
from food.services.subscription_service import get_or_create_free_subscription
import logging

logger = logging.getLogger(__name__)


def _save_with_updated_at(instance, update_fields=None):
    if not update_fields:
        instance.save()
        return instance

    fields = list(update_fields)
    if hasattr(instance, "updated_at") and "updated_at" not in fields:
        fields.append("updated_at")
    instance.save(update_fields=fields)
    return instance


def _apply_updates(instance, validated_data, allowed_fields=None):
    if allowed_fields:
        validated_data = {
            field: value for field, value in validated_data.items() if field in allowed_fields
        }
    for field, value in validated_data.items():
            setattr(instance, field, value)

    return _save_with_updated_at(instance, update_fields=validated_data.keys())


def _ensure_vendor_can_manage_food(vendor):
    if not vendor.is_approved:
        raise ValidationError("Your account must be approved before managing foods.")
    if not vendor.is_active:
        raise ValidationError("Your account must be active to manage foods.")


def _ensure_food_vendor_can_manage(food):
    if not food.vendor:
        raise ValidationError("Food is not associated with a vendor.")
    _ensure_vendor_can_manage_food(food.vendor)


@transaction.atomic
def register_vendor(user, validated_data):
    business_name = validated_data.get("business_name")
    if not business_name:
        raise ValidationError("Business name is required.")

    if Vendor.objects.filter(user=user).exists():
        raise ValidationError("You already have a vendor profile.")

    if Vendor.objects.filter(business_name__iexact=business_name).exists():
        raise ValidationError("This business name is already taken.")

    try:
        vendor = Vendor.objects.create(user=user, **validated_data)
    except IntegrityError as exc:
        raise ValidationError("Vendor profile already exists or business name is already taken.") from exc
    
    return vendor


@transaction.atomic
def update_vendor_profile(vendor, validated_data):
    return _apply_updates(
        vendor, 
        validated_data,
        allowed_fields=[
            "business_name",
            "description",
            "profile_photo",
            "phone",
            "address",  
            "city", 
            "state", 
            "country"
        ]
    )


@transaction.atomic
def approve_vendor(vendor, approved_by=None):
    if vendor.is_approved:
        raise ValidationError("Vendor is already approved")
    vendor.is_approved = True
    vendor.is_active = True
    result = _save_with_updated_at(vendor, update_fields=["is_approved", "is_active"])
    if approved_by:
        logger.info(
            f"Vendor '{vendor.business_name}' approved by user '{approved_by.username}'"
        )
    # send email after transaction commits
    # if transaction fails — email never sent ✅

    transaction.on_commit(
        lambda: send_vendor_status_email.delay(vendor.id, "APPROVED")
    )
    return result


@transaction.atomic
def reject_vendor(vendor, rejected_by=None):
    if vendor.is_approved:
        raise ValidationError("Cannot reject an already approved vendor.")
    vendor.is_active = False
    result = _save_with_updated_at(vendor, update_fields=["is_active"])
    if rejected_by:
        logger.info(
            f"Vendor '{vendor.business_name}' rejected by user '{rejected_by.username}'"
        )
    
    transaction.on_commit(
        lambda: send_vendor_status_email.delay(vendor.id, "REJECTED")
    )
    return result


@transaction.atomic
def deactivate_vendor(vendor, deactivated_by=None):
    if not vendor.is_active:
        raise ValidationError("Vendor is already deactivated.")
    vendor.is_active = False
    result = _save_with_updated_at(vendor, update_fields=["is_active"])
    if deactivated_by:
        logger.info(
            f"Vendor '{vendor.business_name}' deactivated by user '{deactivated_by.username}'"
        )
    
    transaction.on_commit(
        lambda: send_vendor_status_email.delay(vendor.id, "DEACTIVATED")
    )
    return result


@transaction.atomic
def activate_vendor(vendor, activated_by=None):
    if vendor.is_active:
        raise ValidationError("Vendor is already active.")
    if not vendor.is_approved:
        raise ValidationError("Vendor must be approved before activation.")
    vendor.is_active = True
    result = _save_with_updated_at(vendor, update_fields=["is_active"])
    if activated_by:
        logger.info(
            f"Vendor '{vendor.business_name}' activated by user '{activated_by.username}'"
        )
    transaction.on_commit(
        lambda: send_vendor_status_email.delay(vendor.id, "ACTIVATED")
    )
    return result

@transaction.atomic
def create_vendor_food(vendor, validated_data):
    _ensure_vendor_can_manage_food(vendor)

    subscription = get_or_create_free_subscription(vendor)
    plan = subscription.plan

    # 0 = unlimited
    if plan.max_food_listings > 0:
        current_food_count = Food.objects.filter(vendor=vendor).count()

        if current_food_count >= plan.max_food_listings:
            raise ValidationError(
                f"You have reached your plan limit of {plan.max_food_listings} food listings. "
                f"Upgrade your plan to add more."
            )
    
    return Food.objects.create(vendor=vendor, **validated_data)


@transaction.atomic
def update_vendor_food(food, user, validated_data):
    _ensure_food_vendor_can_manage(food)
    return _apply_updates(food, validated_data)


@transaction.atomic
def delete_vendor_food(food):
    _ensure_food_vendor_can_manage(food)

    active_orders = OrderItem.objects.filter(
        food=food, 
        order__status__in=["PENDING", "CONFIRMED", "PREPARING"]
        ).exists()
    
    if active_orders:
        food.available = False
        food.save(update_fields=["available"])
        return "hidden"

    food.delete()
    return "deleted"


@transaction.atomic
def toggle_vendor_food_availability(food):
    _ensure_food_vendor_can_manage(food)
    if not food.available and food.stock == 0:
        raise ValidationError("Cannot mark food available with zero stock.")
    food.available = not food.available
    return _save_with_updated_at(food, update_fields=["available"])
