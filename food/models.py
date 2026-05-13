from django.db import models
from django.db.models import Q, UniqueConstraint
from django.db.models.functions import Lower
from django.contrib.auth.models import User
from django.utils import timezone
from food.utils import save_with_unique_slug
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator


class Category(models.Model):
    name = models.CharField(max_length=70, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            return save_with_unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor")
    business_name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to="vendors/", null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default="Nigeria")
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                Lower("business_name"), name="unique_business_name_ci"
            )
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            return save_with_unique_slug(self, self.business_name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.business_name

class Food(models.Model):
    vendor = models.ForeignKey(Vendor, related_name="foods", null=True, on_delete=models.SET_NULL)
    category = models.ForeignKey(Category, related_name="foods", null=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=70, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="foods/", null=True, blank=True)
    available = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                Lower("name"), 
                "vendor",  
                name="unique_vendor_food_name_ci"
            )
        ]

    def save(self, *args, **kwargs):
        if self.stock == 0:
            self.available = False
        if not self.slug:
            return save_with_unique_slug(self, self.name)
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

    PAYMENT_STATUS = [
        ("UNPAID", "Unpaid"),
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("FAILED", "Failed")
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, related_name="orders", null=True)
    address = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="PENDING")
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    preparing_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    out_for_delivery_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS, default="UNPAID")

    def __str__(self):
        return f"Order {self.id} - {self.user.username} - {self.status}"

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["user", "vendor"],
                condition=Q(status="PENDING"),
                name="unique_pending_order_per_user_per_vendor"
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

    def __str__(self):
        return f"Order {self.order.id} → {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.CASCADE, related_name="food_items")
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"{self.quantity}x {self.food.name}"
    
    @property
    def subtotal(self):
        if self.price_at_purchase is None:
            return 0
        return self.quantity * self.price_at_purchase
    
    def save(self, *args, **kwargs):
        if self.price_at_purchase is None:
            self.price_at_purchase = self.food.price
        super().save(*args, **kwargs)


class Review(models.Model):    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="review", null=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, related_name="reviews", null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1, message="Rating must be at least 1"), MaxValueValidator(5, message="Rating cannot exceed 5")]
    )
    comment = models.TextField(blank=True)
    photo = models.ImageField(upload_to="reviews/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.order and self.vendor != self.order.vendor:
            raise ValidationError("Review vendor must match order vendor.")

    def __str__(self):
        order_id = self.order_id if self.order_id else "unknown"
        return f"Review by {self.user.username} for Order {order_id}" 


class Plan(models.Model):
    PLAN_TYPES = [
        ("FREE", "Free"),
        ("BASIC", "Basic"),
        ("PREMIUM", "Premium")
    ]

    name = models.CharField(max_length=50, choices=PLAN_TYPES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    max_food_listings = models.PositiveIntegerField(default=0) # 0 =unlimited
    max_orders_per_month = models.PositiveIntegerField(default=0) # 0 = unlimited
    priority_listing= models.BooleanField(default=False)
    can_receive_reviews = models.BooleanField(default=False)
    analytics_access = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    STATUS = [
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expired"),
        ("CANCELLED", "Cancelled")
    ]

    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE, related_name="subscription", null=True, blank=True)
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS, default="ACTIVE")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    payment_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan.name}"
    
    def is_valid(self):
        return self.status == "ACTIVE" and self.end_date > timezone.now()   


class SubscriptionHistory(models.Model):
    EVENT = [
        ("SUBSCRIBED", "Subscribed"),
        ("EXPIRED", "Expired"),
        ("EXPIRING_SOON", "Expiring soon"),
        ("CANCELLED", "Cancelled")
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="subscription_history")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    event = models.CharField(max_length=20, choices=EVENT)
    payment_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.vendor.business_name} → {self.event} → {self.plan.name}"
