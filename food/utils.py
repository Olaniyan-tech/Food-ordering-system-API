import uuid
from django.utils.text import slugify
from django.db import IntegrityError, transaction
from food.models import Vendor
from food.selectors import get_vendor_by_id_for_email
import logging

logger = logging.getLogger(__name__)

def save_with_unique_slug(instance, base_text, slug_field="slug", attempts=1):
    model_class = instance.__class__

    if not getattr(instance, slug_field):
        base_slug = slugify(base_text) or "untitled"

        if attempts == 1:
            existing_slugs = set(
                model_class.objects.filter(
                    **{f"{slug_field}__startswith": base_slug}
                ).exclude(pk=instance.pk)
                .values_list(slug_field, flat=True)
            )

            slug = base_slug
            counter = 1
            while slug in existing_slugs:
                slug = f"{base_slug}-{counter}"
                counter +=1
        
        else:
            slug = f"{slugify(base_text)}-{uuid.uuid4().hex[:4]}"
            logger.warning(
                f"Slug collision exceeded 100 attempts for '{base_text}' "
                f"- using UUID fallback: {slug}"
            )

        setattr(instance, slug_field, slug)
    
    try:
        with transaction.atomic():
            instance.save()
    
    except IntegrityError:
        if attempts > 3:
            raise

        setattr(instance, slug_field, None)
        return save_with_unique_slug(instance, base_text, slug_field, attempts + 1)




def get_valid_vendor_for_email(vendor_id):
    try:
        vendor = get_vendor_by_id_for_email(vendor_id)

    except Vendor.DoesNotExist:
        logger.error(
            f"Vendor {vendor_id} not found, skipping email"
        )
        return None

    if not vendor.user:
        logger.critical(
            f"Vendor {vendor_id} exists but has no user attached"
        )
        return None

    return vendor