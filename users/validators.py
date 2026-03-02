import re
from rest_framework import serializers

def validate_phone_format(value):
    if not re.match(r'^\+[1-9]\d{7,14}$', value):
        raise serializers.ValidationError(
            "Phone number must be in international format e.g. +2348076345218"
        )