"""
信号处理程序，用于在文件删除时清理关联的物理文件
"""

import os
import logging
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import File


@receiver(pre_delete, sender=File)
def delete_file_files(sender, instance, **kwargs):
    """
    在File删除前删除关联的物理文件
    这是双重保障，确保即使不通过模型的delete方法删除也能清理文件
    """
    logger = logging.getLogger(__name__)
    
    def _safe_delete(field_file, label, file_id, file_name):
        """安全删除文件，区分文件不存在和权限错误"""
        if not field_file:
            return
        try:
            file_path = field_file.path
            if not os.path.exists(file_path):
                logger.warning(
                    f"[Signal] {label} file not found on disk for file {file_id}: "
                    f"{file_name} (path: {file_path})"
                )
                return
            field_file.delete(save=False)
            logger.info(f"[Signal] Deleted {label} file for file {file_id}: {file_name}")
        except PermissionError as e:
            logger.error(
                f"[Signal] Permission denied deleting {label} file for file {file_id}: "
                f"{file_name} - {str(e)}"
            )
        except Exception as e:
            logger.warning(
                f"[Signal] Could not delete {label} file for file {file_id}: "
                f"{file_name} - {str(e)}"
            )
    
    # 删除预览文件（如果存在）
    _safe_delete(instance.preview, "preview", instance.id, instance.name)
    
    # 删除原始文件（如果存在）
    _safe_delete(instance.file, "original", instance.id, instance.name)