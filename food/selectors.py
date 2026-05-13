from food.models import(
    Food, 
    Order, 
    OrderItem,
    Review, 
    Vendor, 
    Category, 
    Plan, 
    Subscription,
    SubscriptionHistory,
)

from django.db.models import Avg, Count, Sum, Q
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

def get_all_categories():
    return Category.objects.all().order_by("name")

def get_category_by_slug(slug):
    return Category.objects.get(slug=slug)

def get_category_by_id(category_id):
    return Category.objects.get(id=category_id)

def get_available_foods(vendor=None):
    qs = Food.objects.filter(available=True
        ).select_related("vendor__suscription__plan", "category"
        ).order_by("-vendor__subscription__plan__priority_listing", "name") # premium vendors
    
    if vendor:
        qs = qs.filter(vendor=vendor)
    return qs

def get_food_by_id(food_id):
    return Food.objects.select_related("vendor", "category").get(id=food_id)

def get_available_food_by_id(food_id):
    return Food.objects.select_related("vendor", "category").get(id=food_id, available=True)

def get_user_orders(user):
    return Order.objects.prefetch_related(
        "items__food"
    ).filter(user=user).order_by("-created_at")

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
    return Order.objects.select_related("user", "vendor").get(
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
        ).select_related("user", "vendor").order_by("-created_at")

def get_food_reviews_stats(food_id):
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
            "total_reviews": result["total_reviews"] or 0
        }
        cache.set(cache_key, stats, timeout=300)
    
    return stats

def get_all_vendors():
    return Vendor.objects.filter(
        is_approved=True,
        is_active=True
    ).order_by("id")

def get_vendor_by_slug(slug):
    return Vendor.objects.get(slug=slug, is_active=True, is_approved=True)

def get_vendor_by_id(vendor_id):
    return Vendor.objects.get(id=vendor_id)

def get_vendor_by_id_for_email(vendor_id):
    return Vendor.objects.select_related("user").get(id=vendor_id)

def get_pending_vendors():
    return Vendor.objects.filter(is_approved=False).order_by("id")

def get_vendor_foods(vendor, available_only=False):
    qs = Food.objects.filter(vendor=vendor).select_related("category").order_by("id")
    if available_only:
        qs = qs.filter(available=True)
    return qs

def get_vendor_orders(vendor):
    return Order.objects.filter(vendor=vendor).prefetch_related(
        "items__food"
    ).select_related("user").order_by("-created_at")

def get_vendor_order_by_id(vendor, order_id):
    return Order.objects.prefetch_related(
        "items__food"
    ).select_related("user").get(id=order_id, vendor=vendor)

def get_vendor_reviews(vendor):
    return Review.objects.filter(
        vendor=vendor
    ).select_related("user", "order").order_by("-created_at")

def get_vendor_reviews_stats(vendor_id):
    cache_key = f"vendor_reviews_stats_{vendor_id}"
    stats = cache.get(cache_key)

    if stats is None:
        result = Review.objects.filter(
            vendor_id=vendor_id,
        ).aggregate(
            average_rating=Avg("rating"),
            total_reviews=Count("id")
        )
        stats = {
            "average_rating": round(result["average_rating"] or 0, 1),
            "total_reviews": result["total_reviews"] or 0
        }
        cache.set(cache_key, stats, timeout=300)
    
    return stats

def get_vendor_dashboard_stats(vendor):
    cache_key = f"vendor_dashboard_stats_{vendor.id}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    stats = Order.objects.filter(vendor=vendor).aggregate(
        total_orders=Count("id"),
        pending_orders=Count("id", filter=Q(status="PENDING")),
        confirmed_orders=Count("id", filter=Q(status="CONFIRMED")),
        preparing_orders=Count("id", filter=Q(status="PREPARING")),
        ready_orders=Count("id", filter=Q(status="READY")),
        out_for_delivery_orders=Count("id", filter=Q(status="OUT FOR DELIVERY")),
        delivered_orders=Count("id", filter=Q(status="DELIVERED")),
        cancelled_orders=Count("id", filter=Q(status="CANCELLED")),
        total_earnings=Sum("total", filter=Q(payment_status="PAID")),
    )

    result = {
        "total_orders": stats["total_orders"] or 0,
        "total_earnings": stats["total_earnings"] or 0,
        "total_foods": Food.objects.filter(vendor=vendor).count(),

        "order_breakdown": {
            "pending_orders": stats["pending_orders"] or 0,
            "confirmed_orders": stats["confirmed_orders"] or 0,
            "preparing_orders": stats["preparing_orders"] or 0,
            "ready_orders": stats["ready_orders"] or 0,
            "out_for_delivery_orders": stats["out_for_delivery_orders"] or 0,
            "delivered_orders": stats["delivered_orders"] or 0,
            "cancelled_orders": stats["cancelled_orders"] or 0,
        },
    }
    
    cache.set(cache_key, result, timeout=300)
    return result

def get_all_plans():
    return Plan.objects.filter(is_active=True)

def get_plan_by_id(plan_id):
    return Plan.objects.filter(id=plan_id, is_active=True)

def get_subscription_by_reference(reference, vendor):
    return Subscription.objects.select_related("vendor", "plan").get(
        payment_reference=reference,
        vendor=vendor
    )

def get_vendor_subscription(vendor):
    try:
        return vendor.subscription
    except Subscription.DoesNotExist:
        return None

def get_vendor_subscription_by_id_for_email(vendor_id):
    return Vendor.objects.select_related(
        "user", "subscription__plan"
        ).get(id=vendor_id)

def get_vendor_subscription_history(vendor):
    return SubscriptionHistory.objects.filter(
        vendor=vendor
    ).select_related("plan").order_by("-created_at")

def get_vendor_analytics(vendor):
    now = timezone.now()
    this_month = now.replace(day=1, hour=0, minute=0, second=0)
    last_month = (this_month - timedelta(days=1)).replace(day=1)

    orders_this_month = Order.objects.filter(
        items__food__vendor=vendor,
        created_at__gte=this_month,
        status="DELIVERED"
    ).distinct()

    orders_last_month = Order.objects.filter(
        items__food__vendor=vendor,
        created_at__gte=last_month,
        created_at__lt=this_month,
        status="DELIVERED"
    ).distinct()

    revenue_this_month = orders_this_month.aggregate(
        total=Sum("total")
    )["total"] or 0

    revenue_last_month = orders_last_month.aggregate(
        total=Sum("total")
    )["total"] or 0

    top_foods = OrderItem.objects.filter(
        food__vendor=vendor,
        order__status="DELIVERED"
    ).values(
        "food__name"
    ).annotate(
        total_sold=Sum("quantity")
    ).order_by("-total_sold")[:5]

    revenues = {
        "orders_this_month": orders_this_month.count(),
        "orders_last_month": orders_last_month.count(),
        "revenue_this_month": revenue_this_month,
        "revenue_last_month": revenue_last_month,
        "top_foods": list(top_foods),
    }

    return revenues
