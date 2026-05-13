from django.contrib import admin
from food.models import (
    Food, 
    Order, 
    OrderStatusHistory, 
    OrderItem, 
    Category, 
    Review, 
    Vendor,
    Plan,
    Subscription,
    SubscriptionHistory,
)


admin.site.register(Food)
admin.site.register(OrderItem)


class OrderItemInline(admin.StackedInline):
    model = OrderItem
    readonly_fields = ('subtotal',)
    extra = 1

class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = [
        'id', 'user', 'address', 'total', 
        'status',  'created_at', 'updated_at', 'payment_status'
    ]
    
admin.site.register(Order, OrderAdmin)

class OrderHistoryStatusAdmin(admin.ModelAdmin):
    list_display = ['order', 'status', 'changed_by', 'created_at']

admin.site.register(OrderStatusHistory, OrderHistoryStatusAdmin)


class FoodInline(admin.StackedInline):
    model = Food
    extra = 1
    readonly_fields = ['name', 'price']

class CategoryAdmin(admin.ModelAdmin):
    inlines = [FoodInline]

admin.site.register(Category, CategoryAdmin)


class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'order', 'rating', 'comment', 'created_at']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(Review, ReviewAdmin)


class VendorAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'business_name', 'is_active', 'is_approved']
    list_editable = ['is_active', 'is_approved']
    readonly_fields = ['created_at', 'updated_at']    

admin.site.register(Vendor, VendorAdmin)


class PlanAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'price', 'max_food_listings', 
        'max_orders_per_month', 'can_receive_reviews', 
        'priority_listing', 'is_active'
    ]

admin.site.register(Plan, PlanAdmin)


class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'plan', 'status', 'start_date', 'end_date']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(Subscription, SubscriptionAdmin)


class SubscriptionHistoryAdmin(admin.ModelAdmin):
    list_display = ["vendor", "plan", "event", "created_at"]
    readonly_fields = ["vendor", "plan", "event", "payment_reference", "created_at"]