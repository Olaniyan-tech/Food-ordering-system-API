from django.contrib import admin
from food.models import Food, Order, OrderStatusHistory, OrderItem, Category


admin.site.register(Food)
admin.site.register(OrderItem)


class OrderItemInline(admin.StackedInline):
    model = OrderItem
    readonly_fields = ('subtotal',)
    extra = 1

class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ['id', 'user', 'total', 'status', 'date_created', 'updated']
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