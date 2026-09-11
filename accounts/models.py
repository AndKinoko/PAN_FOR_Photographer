from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver

# 新用户默认网盘配额：10GB；None 表示不限额
DEFAULT_QUOTA_BYTES = 10 * 1024 ** 3


def format_bytes(num):
    if num is None:
        return "不限额"
    num = int(num or 0)
    if num < 1024:
        return f"{num} B"
    if num < 1024 ** 2:
        return f"{num / 1024:.1f} KB"
    if num < 1024 ** 3:
        return f"{num / 1024 ** 2:.1f} MB"
    return f"{num / 1024 ** 3:.1f} GB"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # 冻结：可登录、可预览，不可下载原文件 / 不可上传 / 不可创建分享
    is_frozen = models.BooleanField(default=False, verbose_name="冻结")
    # 配额：None 表示不限额
    quota_bytes = models.BigIntegerField(
        null=True, blank=True, default=DEFAULT_QUOTA_BYTES, verbose_name="配额(字节)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"

    def usage_bytes(self):
        from storage.models import File

        total = File.objects.filter(owner=self.user).aggregate(s=Sum("size"))["s"]
        return int(total or 0)

    def file_count(self):
        from storage.models import File

        return File.objects.filter(owner=self.user).count()

    def quota_percent(self):
        if not self.quota_bytes:
            return 0
        try:
            return min(100, round(self.usage_bytes() * 100 / self.quota_bytes, 1))
        except ZeroDivisionError:
            return 0


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
