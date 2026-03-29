from django.core.exceptions import ValidationError
from food.models import Review
from django.core.cache import cache

def create_review(order, user, validated_data):
    if order.user != user:
        raise ValidationError("You can only review your own orders")
    
    if order.status != "DELIVERED":
        raise ValidationError("You can only review delivered orders")
    
    if hasattr(order, "review"):
        raise ValidationError("You have already reviewed this order")
    
    review = Review.objects.create(
        order=order,
        user=user,
        **validated_data
    )

    food_ids = order.items.values_list("food__id", flat=True)
    for food_id in food_ids:
        cache.delete(f"food_reviews_{food_id}")
        cache.delete(f"food_review_stats_{food_id}")
    
    return review



