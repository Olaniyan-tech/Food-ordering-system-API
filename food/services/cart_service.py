from food.models import Food, Order, OrderItem
from django.db import transaction
from django.db.models import F, Sum
from django.core.exceptions import ValidationError

@transaction.atomic
def add_item_to_cart(user, food, quantity=1):    
    if not food.available:
        raise ValidationError("Food is not available")
    
    food = Food.objects.select_for_update().get(id=food.id)
    
    if quantity > food.stock:
        raise ValidationError("Not enough stock for this food item")
    
    order = (
        Order.objects.select_for_update()
        .filter(user=user, vendor=food.vendor, status="PENDING")
        .first()
    )

    if not order:       
        order = Order.objects.create(user=user, vendor=food.vendor, status="PENDING")

    item, created = OrderItem.objects.select_for_update().get_or_create(
        order=order, 
        food=food,
        defaults={"quantity": quantity, 'price_at_purchase': food.price}
    )
    
    if not created:
        item.quantity = F("quantity") + quantity
        item.save()
        item.refresh_from_db()
    
    update_order_total(order)   
    return order

@transaction.atomic
def remove_item_from_cart(user, item_id, action):
    try:
        item = OrderItem.objects.select_related(
            "food__vendor", "order"
        ).get(id=item_id)

        item.refresh_from_db()
        food = Food.objects.select_related("vendor").get(id=item.food_id)
        
    except OrderItem.DoesNotExist:
        raise ValidationError("Item not found in Cart")
    
    order = Order.objects.select_for_update().filter(
        user=user, 
        vendor=food.vendor, 
        status="PENDING").first()
    
    if not order:
        raise ValidationError("Cart is empty")
    
    if item.order_id != order.id:
        raise ValidationError("Item does not belong to your cart")

    if action == "decrease":
        item.quantity = F("quantity") - 1
        item.save()
        item.refresh_from_db()

        if item.quantity <= 0:
            item.delete()
            
    elif action == "delete":
        item.delete()

    else:
        raise ValidationError("Invalid action")
    
    if not order.items.exists():
        order.delete()
        return None
    
    update_order_total(order)
    return order

def update_order_total(order):
    total = order.items.aggregate(total=Sum(F("quantity") * F("price_at_purchase")))["total"] or 0
    order.total = total
    order.save(update_fields=["total", "updated_at"])


