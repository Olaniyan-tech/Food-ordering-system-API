from django.contrib import admin
from food.models import Food, Order, OrderStatusHistory, OrderItem, Category, Review, Vendor


admin.site.register(Food)
admin.site.register(OrderItem)


class OrderItemInline(admin.StackedInline):
    model = OrderItem
    readonly_fields = ('subtotal',)
    extra = 1

class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ['id', 'user', 'address', 'total', 'status',  'created_at', 'updated_at', 'payment_status']
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
    readonly_fields = ['created_at', 'updated_at']
admin.site.register(Vendor, VendorAdmin)