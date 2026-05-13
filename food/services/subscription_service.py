from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from food.models import Food, Order, Plan, Subscription, SubscriptionHistory


def record_subscription_history(vendor, plan, event, payment_reference=""):
    SubscriptionHistory.objects.create(
        vendor=vendor,
        plan=plan,
        event=event,
        payment_reference=payment_reference
    )


def get_or_create_free_subscription(vendor):
    try:
        return vendor.subscription
    except Subscription.DoesNotExist:
        free_plan = Plan.objects.get(name="FREE")
        subscription = Subscription.objects.create(
            vendor=vendor,
            plan=free_plan,
            status="ACTIVE",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=36500)
        )
        record_subscription_history(vendor, free_plan, "SUBSCRIBED")
        return subscription
    

def subscribe_vendor(vendor, plan_id, payment_reference=None):
    from food.tasks import send_subscription_email
    free_plan = Plan.objects.get(name="FREE")

    try:
        plan = Plan.objects.get(id=plan_id, is_active=True)
    except Plan.DoesNotExist:
        raise ValidationError("Plan not found")

    if plan == free_plan:
        raise ValidationError("Vendor is already on the free plan.")
    
    if not payment_reference:
        raise ValidationError("Payment reference is required for paid plans.")
    
    event = "SUBSCRIBED"

    try:
        subscription = vendor.subscription
        if subscription.is_valid() and subscription.plan == plan:
            raise ValidationError("Vendor is already subscribed to this plan")

        subscription.plan = plan
        subscription.status = "ACTIVE"
        subscription.start_date = timezone.now()
        subscription.end_date = timezone.now() + timedelta(days=30)
        subscription.payment_reference = payment_reference
        subscription.save(update_fields=[
            "plan", "status", "start_date",
            "end_date", "payment_reference", "updated_at"
        ])
    
    except Subscription.DoesNotExist:
        subscription = Subscription.objects.create(
            vendor=vendor,
            plan=plan,
            status="ACTIVE",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            payment_reference=payment_reference
        )
    
    record_subscription_history(vendor, plan, event, payment_reference)
    send_subscription_email.delay(vendor.id, "SUBSCRIBED")

    return subscription


def cancel_subscription(vendor):
    from food.tasks import send_subscription_email
    try:
        subscription = vendor.subscription
    except Subscription.DoesNotExist:
        raise ValidationError("Vendor has no active subscription")
    
    if subscription.status == "CANCELLED":
        raise ValidationError("Subscription is already cancelled")
    
    free_plan = Plan.objects.get(name="FREE")
    subscription.status = "CANCELLED"
    subscription.plan = free_plan
    subscription.end_date = timezone.now()
    subscription.save(update_fields=[
        "status", "plan", "end_date", "updated_at"
    ])

    record_subscription_history(vendor, free_plan, "CANCELLED")
    send_subscription_email.delay(vendor.id, "CANCELLED")
    return subscription


def check_subscription_status(vendor):
    from food.tasks import send_subscription_email
    try:
        subscription = vendor.subscription
        if subscription.status == "ACTIVE" and subscription.end_date < timezone.now():
            free_plan = Plan.objects.get(name="FREE")
            subscription.status = "EXPIRED"
            subscription.plan = free_plan
            subscription.save(update_fields=[
                "status", "plan", "updated_at"
            ])

            record_subscription_history(vendor, free_plan, "EXPIRED")
            send_subscription_email.delay(vendor.id, "EXPIRED")
        
        return subscription

    except Subscription.DoesNotExist:
        return get_or_create_free_subscription(vendor)


def add_food_listing(vendor, food_data):
    #Check subscription limit before allowing vendor to add more food

    subscription = vendor.subscription
    plan = subscription.plan

    # 0 = unlimited
    if plan.max_food_listings > 0:
        current_food_count = Food.objects.filter(vendor=vendor).count()

        if current_food_count >= plan.max_food_listings:
            raise ValidationError(
                f"You have reached your plan limit of {plan.max_food_listings} food listings. "
                f"Upgrade your plan to add more."
            )
    
    return Food.objects.create(vendor=vendor, **food_data)


def check_vendor_order_limit(vendor):
    plan = vendor.subscription.plan
    if plan.max_orders_per_month == 0:
        return # unlimited
    
    # count orders this month
    this_month = timezone.now().replace(day=1, hour=0, minute=0, second=0)
    monthly_orders = Order.objects.filter(
        items__food__vendor=vendor,
        created_at__gte=this_month
    ).distinct().count()

    if monthly_orders >= plan.max_orders_per_month:
        raise ValidationError(
            f"You have reached your plan limit of "
            f"{plan.max_orders_per_month}. You need to upgrage."
        )
    


