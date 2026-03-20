from django.db import models
from django.contrib.auth.models import User
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
    password = models.CharField(max_length=100, blank=True)
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
        return f"/share/{self.id}/"
    
    def increment_download(self):
        self.download_count += 1
        self.save()
    
    @classmethod
    def create_share(cls, file, owner, expires_hours=None, password=None):
        """Create a new file share"""
        share = cls.objects.create(
            file=file,
            owner=owner,
            password=password or ''
        )
        
        if expires_hours:
            share.expires_at = timezone.now() + timedelta(hours=expires_hours)
            share.save()
        
        return share