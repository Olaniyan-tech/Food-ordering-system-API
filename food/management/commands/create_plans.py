from django.core.management.base import BaseCommand
from food.models import Plan

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        Plan.objects.get_or_create(
            name="FREE",
            defaults={
                "price": 0,
                "max_food_listings": 5,
                "max_orders_per_month": 50,
                "can_receive_reviews": False,
                "priority_listing": False,
                "analytics_access": False,
                "description": "List up to 5 foods, 50 orders/month"
            }
        )
        Plan.objects.get_or_create(
            name="BASIC",
            defaults={
                "price": 5000,
                "max_food_listings": 20,
                "max_orders_per_month": 200,
                "can_receive_reviews": True,
                "priority_listing": False,
                "analytics_access": False,
                "description": "List up to 20 foods, 150 orders/month + reviews"
            }
        )
        Plan.objects.get_or_create(
            name="PREMIUM",
            defaults={
                "price": 15000,
                "max_food_listings": 0, #unlimited
                "max_orders_per_month": 0, #unlimited
                "can_receive_reviews": True,
                "priority_listing": True,
                "analytics_access": True,
                "description": "Unlimited listings + priority placement + analytics"
            }
        )
        self.stdout.write(self.style.SUCCESS("Plans created successfully"))
        