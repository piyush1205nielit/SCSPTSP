"""Template context processor exposing user scope (center / admin)."""


def user_scope(request):
    user = getattr(request, "user", None)
    is_admin = bool(user and user.is_authenticated and user.is_superuser)
    user_center = ""
    if user and user.is_authenticated and not is_admin:
        try:
            from portal.models import UserProfile

            profile = UserProfile.objects.filter(user=user).first()
            if profile and profile.center_name:
                user_center = profile.center_name
        except Exception:
            user_center = ""
    return {
        "is_admin_user": is_admin,
        "user_center": user_center,
    }
