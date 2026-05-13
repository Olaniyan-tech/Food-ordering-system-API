from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import OrderItem

@receiver(post_save, sender=OrderItem)
def update_total_order(sender, instance, **kwargs):
    order = instance.order
    order.total = sum(item.subtotal for item in order.items.all())
    order.save(update_fields=["total"])