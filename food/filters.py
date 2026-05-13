import django_filters
from food.models import Food, Order, Review

class FoodFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category__id")
    category_name = django_filters.CharFilter(field_name="category__name", lookup_expr="icontains")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = Food
        fields = ["category", "category_name", "min_price", "max_price"]


class OrderFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    payment_status = django_filters.CharFilter(field_name="payment_status", lookup_expr="exact")

    class Meta:
        model = Order
        fields = ["status", "payment_status"]


class ReviewFilter(django_filters.FilterSet):
    rating = django_filters.NumberFilter(field_name="rating") 
    min_rating = django_filters.NumberFilter(field_name="rating", lookup_expr="gte")
    max_rating = django_filters.NumberFilter(field_name="rating", lookup_expr="lte")

    class Meta:
        model = Review
        fields = ["rating", "min_rating", "max_rating"]
    
