from rest_framework import serializers
from food.models import Food, Order, OrderItem
import re
from users.validators import validate_phone_format

class FoodSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Food
        fields = ("id", "name", "price", "descriptions", "image_url", "category")


    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image_url:
            if request:
                return request._request.build_absolute_uri(obj.image_url.url)
            return obj.image_url.url
        return None

class OrderItemSerializer(serializers.ModelSerializer):
    food = FoodSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "food", "quantity", "price_at_purchase", "subtotal")

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
            if hasattr(instance.user, "profile") and instance.user.profile.phone:
                phone = instance.user.profile.phone
            else:
                raise serializers.ValidationError("Phone number is required.")
        
        instance.phone = phone
        instance.save(update_fields=["address", "phone"])
        return instance
