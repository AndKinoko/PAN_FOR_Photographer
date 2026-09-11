from .models import format_bytes


def profile_info(request):
    """向所有模板注入当前用户的冻结状态与容量信息。"""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}
    try:
        profile = user.profile
    except Exception:
        return {}
    usage = profile.usage_bytes()
    quota = profile.quota_bytes
    return {
        "is_frozen": profile.is_frozen,
        "storage_usage": usage,
        "storage_usage_display": format_bytes(usage),
        "storage_quota_display": format_bytes(quota),
        "storage_quota_percent": profile.quota_percent(),
    }
