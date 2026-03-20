"""
信号处理程序，用于在文件删除时清理关联的物理文件
"""

import logging
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import File


@receiver(pre_delete, sender=File)
def delete_file_files(sender, instance, **kwargs):
    """
    在File删除前删除关联的文件
    这是双重保障，确保即使不通过模型的delete方法删除也能清理文件
    """
    logger = logging.getLogger(__name__)
    
    # 删除预览文件（如果存在）
    if instance.preview:
        try:
            instance.preview.delete(save=False)
            logger.info(f"[Signal] Deleted preview file for file {instance.id}: {instance.name}")
        except Exception as e:
            logger.warning(f"[Signal] Could not delete preview file for file {instance.id}: {str(e)}")
    
    # 删除原始文件（如果存在）
    if instance.file:
        try:
            instance.file.delete(save=False)
            logger.info(f"[Signal] Deleted original file for file {instance.id}: {instance.name}")
        except Exception as e:
            logger.warning(f"[Signal] Could not delete original file for file {instance.id}: {str(e)}")