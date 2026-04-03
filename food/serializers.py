from rest_framework import serializers
from food.models import Food, Order, OrderItem, Review, Category, Vendor
from users.validators import validate_phone_format
from drf_spectacular.utils import extend_schema_field


def validate_vendor_phone(value, instance):
    validate_phone_format(value)
    if Vendor.objects.filter(phone=value).exclude(id=instance.id).exists():
        raise serializers.ValidationError("This phone number is already used by another vendor")
    return value


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class VendorRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = (
            "business_name",
            "description",
            "logo",
            "phone",
            "address",
            "city",
            "state",
            "country",
        )


class VendorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = (
            "id", 
            "business_name",
            "description",
            "logo",
            "city",
            "state",
            "is_active"
        )


class VendorUpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = (
            "business_name",
            "description",
            "logo",
            "phone",
            "address",
            "city",
            "state",
            "country",
            "slug",
            "is_active",   
            "is_approved"
        )
        read_only_fields = ("slug", "is_active", "is_approved")


    def validate_phone(self, value):
        return validate_vendor_phone(value, self.instance)
   

class VendorDashboardSerializer(serializers.ModelSerializer):
    total_foods = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    is_approved = serializers.BooleanField(read_only=True)

    class Meta:
        model = Vendor
        fields = (
            "id",
            "business_name",
            "slug",
            "description",
            "logo",
            "phone",
            "address",
            "city",
            "state",
            "country",
            "is_active",
            "is_approved",
            "total_foods",
            "total_orders",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("slug", "is_active", "created_at", "updated_at")

    @extend_schema_field(serializers.IntegerField())
    def get_total_foods(self, obj):
        return obj.foods.count()

    @extend_schema_field(serializers.IntegerField())
    def get_total_orders(self, obj):
        return obj.orders.count()

    def validate_phone(self, value):
        return validate_vendor_phone(value, self.instance)


class FoodSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    vendor = VendorProfileSerializer(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Food
        fields = (
            "id", 
            "vendor", 
            "name", 
            "price", 
            "description", 
            "image", 
            "category", 
            "stock"
        )
    
    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image:
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class FoodWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = (
            "id", 
            "category", 
            "name",  
            "description", 
            "price",
            "image",
            "available", 
            "stock",
        )
    
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0")
        return value
    
    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative")
        return value
        

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
    vendor = VendorProfileSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", 
            "user", 
            "vendor", 
            "address", 
            "phone", 
            "total", 
            "status", 
            "payment_status", 
            "created_at", 
            "updated_at", 
            "items"
        )


class AddToCartSerializer(serializers.Serializer):
    food = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)

   
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
    user = serializers.CharField(source="user.username", read_only=True)
    vendor = VendorProfileSerializer(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id", 
            "user", 
            "vendor",
            "order", 
            "rating", 
            "comment", 
            "photo", 
            "created_at", 
            "updated_at"
        )
        read_only_fields = ("order",)

    def validate(self, data):
        order = self.instance.order if self.instance else data.get("order")
        if order:
            data["vendor"] = order.vendor
        return data


   
