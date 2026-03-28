from rest_framework import serializers
from food.models import Food, Order, OrderItem, Review
from users.validators import validate_phone_format
from drf_spectacular.utils import extend_schema_field

class FoodSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Food
        fields = ("id", "name", "price", "descriptions", "image_url", "category", "stock")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image_url:
            if request:
                return request._request.build_absolute_uri(obj.image_url.url)
            return obj.image_url.url
        return None


class OrderItemSerializer(serializers.ModelSerializer):
    food = FoodSerializer(read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ("id", "food", "quantity", "price_at_purchase", "subtotal")
    
    @extend_schema_field(serializers.DecimalField(max_digits=10, decimal_places=2))
    def get_subtotal(self, obj):
        return obj.subtotal


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Order
        fields = ("id", "user", "address", "phone", "total", "status", "date_created", "items")


class AddToCartSerializer(serializers.ModelSerializer):
    food = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    class Meta:
        model = OrderItem
        fields = ("food", "quantity")
   

class OrderDeliveryDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = Order
        fields = ("address", "phone")
    
    def validate_address(self, value):
        if not value:
            raise serializers.ValidationError("Address is required for checkout.")
        return value
    
    def validate_phone(self, value):
        validate_phone_format(value)
        return value
    
    def update(self, instance, validated_data):
        instance.address = validated_data.get("address", instance.address)

        if not instance.address:
            raise serializers.ValidationError("Address is required")

        phone = validated_data.get("phone")
        if not phone:
            if instance.phone:
                phone = instance.phone
            elif hasattr(instance.user, "profile") and instance.user.profile.phone:
                phone = instance.user.profile.phone
            else:
                raise serializers.ValidationError("Phone number is required.")
        
        instance.phone = phone
        instance.save(update_fields=["address", "phone"])
        return instance


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "username", "rating", "comment", "photo", "created_at", "updated_at"]
        read_only_fields = ["id", "username", "created_at", "updated_at"]
    
    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value
    
