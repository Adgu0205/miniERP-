from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile, Role


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, "profile"):
        role = Role.ADMIN if instance.is_superuser else Role.SALES
        Profile.objects.create(user=instance, role=role)
