from django.db import models
from django.db.models import Q, UniqueConstraint
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify


# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=70, db_index=True)
    slug = models.SlugField(max_length=70, unique=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Food(models.Model):
    category = models.ForeignKey(Category, related_name="food", null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=70, db_index=True)
    slug = models.SlugField(max_length=70, db_index=True, blank=True)
    descriptions = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.ImageField(upload_to="images/", null=True, blank=True)
    available = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    # class Meta:
    #     ordering = ('category', 'name',)
    #     index_together = (('id', 'slug'), )

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS = [
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("PREPARING", "Preparing"),
        ("READY", "Ready for Pickup"),
        ("OUT FOR DELIVERY", "Out for delivery"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        #("REFUNDED", "Refunded")
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    
    address = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="PENDING")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    date_created = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["user"],
                condition=Q(status="PENDING"),
                name="unique_pending_order_per_user"
            )
        ]
    
    
    def save(self, *args, **kwargs):
        if not self.phone and hasattr(self.user, "profile"):
            self.phone = self.user.profile.phone
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, related_name="status_history", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Order.STATUS)
    changed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]



class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name="food_items")
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    @property
    def subtotal(self):
        return self.quantity * self.price_at_purchase
    
    def save(self, *args, **kwargs):
        if self.price_at_purchase is None:
            self.price_at_purchase = self.food.price
        super().save(*args, **kwargs)

