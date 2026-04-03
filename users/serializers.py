from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Profile
from users.validators import validate_phone_format

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True)
    

    class Meta:
        model = User
        fields = ["username", "email", "phone", "password"]
    
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate_phone(self, value):
        validate_phone_format(value)
        
        if Profile.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        
        return value
    
    def validate_password(self, value):
        try:
            validate_password(value)
        except ValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value
    
    def create(self, validated_data):
        phone = validated_data.pop("phone")


        if Profile.objects.filter(phone=phone).exists():
            raise serializers.ValidationError({"phone": "Phone number already exists."})

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )

        Profile.objects.create(user=user, phone=phone)

        return user


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", required=True)
    email = serializers.EmailField(source="user.email", required=True)
    phone = serializers.CharField(required=False)

    class Meta:
        model = Profile
        fields = ("id", "username", "email", "phone")
        read_only_fields = ("id",)
    
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exclude(id=self.instance.user.id).exists():
            raise ValidationError("Email already exists")
        return value
    
    def validate_phone(self, value):
        validate_phone_format(value)
        if Profile.objects.filter(phone=value).exclude(id=self.instance.user.id).exists():
            raise serializers.ValidationError("Phone number already exists")
        return value

    def update(self, instance, validated_data):
        # Update User fields
        user_data = validated_data.pop("user", {})
        user = instance.user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        # Update Profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance