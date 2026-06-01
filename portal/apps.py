from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = 'portal'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from django.db.models.signals import post_save
        from django.contrib.auth.models import User
        from .models import UserProfile

        def create_profile(sender, instance, created, **kwargs):
            if created:
                UserProfile.objects.get_or_create(user=instance)

        post_save.connect(create_profile, sender=User)
