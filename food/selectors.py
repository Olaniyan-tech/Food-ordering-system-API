from food.models import Food, Order, Review
from django.db.models import Avg, Count
from django.core.cache import cache

def get_available_foods():
    foods = cache.get("available_foods")

    if foods is None:
        foods = list(Food.objects.filter(available=True))
        cache.set("available_foods", foods, timeout=300)

    return foods

def get_available_food_by_id(food_id):
    return Food.objects.get(id=food_id, available=True)

def get_user_orders(user):
    return Order.objects.prefetch_related(
        "items__food"
    ).filter(user=user).order_by("-date_created")

def get_pending_order(user):
    return Order.objects.prefetch_related(
        "items__food"
    ).filter(user=user, status="PENDING").first()

def get_order_by_id(order_id):
    return Order.objects.prefetch_related(
        "items__food"
    ).get(id=order_id)

def get_user_order_by_id(order_id, user):
    return Order.objects.prefetch_related(
        "items__food"
    ).get(id=order_id, user=user)

def get_order_by_id_for_email(order_id):
    return Order.objects.select_related(
        "user"
    ).get(id=order_id)

def get_order_by_reference(reference, user):
    return Order.objects.get(
        payment_reference=reference, 
        user=user
    )


def get_order_review(order):
    try:
        return order.review
    except Review.DoesNotExist:
        return None

def get_food_reviews(food_id):
    cache_key = f"food_reviews_{food_id}"
    reviews = cache.get(cache_key)

    if reviews is None:
        reviews = list(Review.objects.filter(
            order__items__food__id=food_id
        ).select_related("user").order_by("-created_at"))

        cache.set(cache_key, reviews, timeout=300)
    
    return reviews


def get_food_review_stats(food_id):
    cache_key = f"food_reviews_stats_{food_id}"
    stats = cache.get(cache_key)

    if stats is None:
        result = Review.objects.filter(
            order__items__food__id=food_id
        ).aggregate(
            average_rating=Avg("rating"),
            total_reviews=Count("id")
        )

        stats = {
            "average_rating": round(result["average_rating"] or 0, 1),
            "total_reviews": result["total_reviews"]
        }
        cache.set(cache_key, stats, timeout=300)
    
    return stats



# def get_food_by_id(food_id):
#     return Food.objects.get(id=food_id)

# def get_foods_by_category(category_slug):
#     return Food.objects.filter(
#         category__slug=category_slug,
#         available=True
#     ).select_related("category")
