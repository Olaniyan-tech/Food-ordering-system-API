from food.models import Food, Order, Review
from django.db.models import Avg, Count

def get_available_foods():
    return Food.objects.filter(available=True)

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
    return Review.objects.filter(
        order__items__food__id=food_id
    ).select_related("user").order_by("-created_at")


def get_food_review_stats(food_id):
    stats = Review.objects.filter(
        order__items__food__id=food_id
    ).aggregate(
        average_rating=Avg("rating"),
        total_reviews=Count("id")
    )
    return {
        "average_rating": round(stats["average_rating"] or 0, 1),
        "total_reviews": stats["total_reviews"]
    }



# def get_food_by_id(food_id):
#     return Food.objects.get(id=food_id)

# def get_foods_by_category(category_slug):
#     return Food.objects.filter(
#         category__slug=category_slug,
#         available=True
#     ).select_related("category")
