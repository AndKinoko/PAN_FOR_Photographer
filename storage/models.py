from django.db import models
from django.contrib.auth.models import User
import os
import logging
from uuid import uuid4
from PIL import Image
import tempfile
import rawpy
import imageio
import numpy as np

def user_directory_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    ext = filename.split('.')[-1]
    filename = f"{uuid4().hex}.{ext}"
    return f'user_{instance.owner.id}/{filename}'

def preview_directory_path(instance, filename):
    # Preview images will be stored in MEDIA_ROOT/user_<id>/previews/<filename>
    ext = 'jpg'  # Preview images are always JPEG
    filename = f"{uuid4().hex}.{ext}"
    return f'user_{instance.owner.id}/previews/{filename}'

class Folder(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        unique_together = ['name', 'owner', 'parent']
    
    def __str__(self):
        return self.name
    
    @property
    def path(self):
        if self.parent:
            return f"{self.parent.path}/{self.name}"
        return self.name
    
    def get_files(self):
        return self.files.all()
    
    def get_subfolders(self):
        return self.subfolders.all()

class File(models.Model):
    name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=user_directory_path)
    preview = models.ImageField(upload_to=preview_directory_path, null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE, null=True, blank=True, related_name='files')
    size = models.BigIntegerField(default=0)  # Size in bytes
    file_type = models.CharField(max_length=50, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Set file type based on extension
        if not self.file_type:
            ext = os.path.splitext(self.original_name)[1].lower()
            self.file_type = ext[1:] if ext else 'unknown'
        
        # Set size safely
        try:
            if self.file and hasattr(self.file, 'size'):
                self.size = self.file.size
            else:
                self.size = 0
        except (AttributeError, ValueError) as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not get file size for {self.original_name}: {e}")
            self.size = 0
        
        # Generate preview for image and RAW files
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new and self.file:
            logger = logging.getLogger(__name__)
            logger.info(f"Generating preview for new file {self.id}: {self.name} (type: {self.file_type})")
            try:
                self.generate_preview()
                logger.info(f"Preview generation completed for file {self.id}")
            except Exception as e:
                logger.error(f"Error generating preview for file {self.id}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
    
    def generate_preview(self):
        """Generate preview image for the file"""
        try:
            # Define supported image formats
            image_formats = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'tif']
            # Define RAW formats
            raw_formats = ['nef', 'cr2', 'cr3', 'crw', 'arw', 'sr2', 'srf', 'dng', 'raf', 'orf', 'rw2', 'nrw']
            
            file_ext = self.file_type.lower()
            
            if file_ext in image_formats:
                # Regular image file
                self._generate_image_preview()
            elif file_ext in raw_formats:
                # RAW file
                self._generate_raw_preview()
            else:
                # Not an image or RAW file, no preview
                logger = logging.getLogger(__name__)
                logger.info(f"File type {file_ext} does not support preview generation")
                return
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating preview for file {self.id}: {str(e)}")
    
    def _generate_image_preview(self):
        """Generate preview for regular image files"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                # Open the image
                with Image.open(self.file.path) as img:
                    # Convert to RGB if necessary
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    
                    # Resize to max 800x800 while maintaining aspect ratio
                    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                    
                    # Save as JPEG
                    img.save(tmp_file.name, 'JPEG', quality=85)
                
                # Save to preview field
                with open(tmp_file.name, 'rb') as f:
                    self.preview.save(f'{self.name}_preview.jpg', f, save=True)
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating image preview for file {self.id}: {str(e)}")
    
    def _generate_raw_preview(self):
        """Generate preview for RAW files"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                # Open RAW file
                with rawpy.imread(self.file.path) as raw:
                    # Process RAW image
                    rgb = raw.postprocess()
                
                # Convert numpy array to PIL Image
                img = Image.fromarray(rgb)
                
                # Resize to max 800x800 while maintaining aspect ratio
                img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                
                # Save as JPEG
                img.save(tmp_file.name, 'JPEG', quality=85)
                
                # Save to preview field
                with open(tmp_file.name, 'rb') as f:
                    self.preview.save(f'{self.name}_preview.jpg', f, save=False)
                
                # Save the model to update the preview field
                self.save()
                
                # Clean up temp file
                try:
                    os.unlink(tmp_file.name)
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not delete temp file {tmp_file.name}: {str(e)}")
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating RAW preview for file {self.id}: {str(e)}")
            # Fallback: try to extract embedded JPEG preview if available
            self._extract_embedded_preview()
    
    def _extract_embedded_preview(self):
        """Try to extract embedded JPEG preview from RAW file"""
        try:
            with rawpy.imread(self.file.path) as raw:
                # Check if there's an embedded JPEG preview
                if hasattr(raw, 'extract_thumb') and raw.thumb_format == rawpy.ThumbFormat.JPEG:
                    thumb = raw.extract_thumb()
                    
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                        # Save the thumbnail
                        with open(tmp_file.name, 'wb') as f:
                            f.write(thumb.data)
                        
                        # Open and resize if needed
                        with Image.open(tmp_file.name) as img:
                            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                            img.save(tmp_file.name, 'JPEG', quality=85)
                        
                        # Save to preview field
                        with open(tmp_file.name, 'rb') as f:
                            self.preview.save(f'{self.name}_preview.jpg', f, save=False)
                        
                        # Save the model to update the preview field
                        self.save()
                        
                        # Clean up temp file
                        try:
                            os.unlink(tmp_file.name)
                        except Exception as e:
                            logger = logging.getLogger(__name__)
                            logger.warning(f"Could not delete temp file {tmp_file.name}: {str(e)}")
                        
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not extract embedded preview for file {self.id}: {str(e)}")
    
    @property
    def preview_url(self):
        """Return preview URL or original file URL if no preview available"""
        if self.preview:
            return self.preview.url
        elif self.file_type.lower() in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'tif']:
            return self.file.url
        else:
            return None
    
    @property
    def formatted_size(self):
        """Return human readable file size"""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} MB"
        else:
            return f"{self.size / (1024 * 1024 * 1024):.1f} GB"
    
    def get_download_url(self):
        return self.file.url
    
    def delete(self, *args, **kwargs):
        """重写delete方法，确保删除文件时同时删除预览图"""
        logger = logging.getLogger(__name__)
        
        # 删除预览文件（如果存在）
        if self.preview:
            try:
                self.preview.delete(save=False)
                logger.info(f"Deleted preview file for file {self.id}: {self.name}")
            except Exception as e:
                logger.warning(f"Could not delete preview file for file {self.id}: {str(e)}")
        
        # 删除原始文件（如果存在）
        if self.file:
            try:
                self.file.delete(save=False)
                logger.info(f"Deleted original file for file {self.id}: {self.name}")
            except Exception as e:
                logger.warning(f"Could not delete original file for file {self.id}: {str(e)}")
        
        # 调用父类的delete方法删除数据库记录
        super().delete(*args, **kwargs)