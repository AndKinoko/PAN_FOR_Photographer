from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.urls import reverse
from storage.models import File
import uuid
from datetime import timedelta
from django.utils import timezone

class FileShare(models.Model):
    """Model for file sharing"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='shares')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='file_shares')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    password = models.CharField(max_length=128, blank=True)
    download_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.file.name} - {self.owner.username}"
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def is_valid(self):
        return self.is_active and not self.is_expired
    
    @property
    def share_url(self):
        return reverse('share:share_access', args=[self.id])
    
    def increment_download(self):
        self.download_count += 1
        self.save()
    
    @classmethod
    def create_share(cls, file, owner, expires_hours=None, password=None):
        """Create a new file share"""
        # 对密码进行哈希处理，避免明文存储
        hashed_password = make_password(password) if password else ''
        
        share = cls.objects.create(
            file=file,
            owner=owner,
            password=hashed_password
        )
        
        if expires_hours:
            share.expires_at = timezone.now() + timedelta(hours=expires_hours)
            share.save()
        
        return share
    
    def verify_password(self, raw_password):
        """验证分享密码"""
        if not self.password:
            return True
        return check_password(raw_password, self.password)