from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db import IntegrityError, transaction
from food.models import Review
from food.services.subscription_service import get_or_create_free_subscription


def _food_reviews_stats_cache_key(food_id):
    return f"food_reviews_stats_{food_id}"

def _vendor_reviews_stats_cache_key(vendor_id):
    return f"vendor_reviews_stats_{vendor_id}"

def _invalidate_review_stats_cache(order):
    food_ids = set(order.items.values_list("food_id", flat=True).distinct())
    cache_keys = [
        _food_reviews_stats_cache_key(food_id)
        for food_id in food_ids
        if food_id is not None
    ]
    if order.vendor_id:
        cache_keys.append(_vendor_reviews_stats_cache_key(order.vendor_id))
    if cache_keys:
        cache.delete_many(cache_keys)

@transaction.atomic
def create_review(order, user, validated_data):
    if order.user != user:
        raise ValidationError("You can only review your own orders")
    
    if order.status != "DELIVERED":
        raise ValidationError("You can only review delivered orders")
    
    if Review.objects.filter(order_id=order.id).exists():
        raise ValidationError("You have already reviewed this order")
    
    # Check if vendor can accept reviews
    vendors = set(item.food.vendor for item in order.items.select_related(
        "food__vendor__subscription__plan")
    )
    
    for vendor in vendors:
        subscription = get_or_create_free_subscription(vendor)
        if not subscription.plan.can_receive_reviews:
            raise ValidationError(
                f"{vendor.business_name} does not accept reviews on their current plan"
            )
        
    data = dict(validated_data)
    data.pop("vendor", None)
    data.pop("order", None)
    
    review = Review(
        order=order,
        user=user,
        vendor=order.vendor,
        **data
    )
    try:
        review.full_clean()
        review.save()
    except IntegrityError as exc:
        raise ValidationError("You have already reviewed this order") from exc

    _invalidate_review_stats_cache(order)
    
    return review


