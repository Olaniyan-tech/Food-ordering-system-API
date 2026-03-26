from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from users.tasks import send_welcome_email
from django.contrib.auth.models import User


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        pass


@receiver(post_save, sender=User)
def send_welcome_on_register(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: send_welcome_email.delay(instance.id))