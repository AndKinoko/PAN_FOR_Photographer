from django.apps import AppConfig


class StorageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'storage'
    
    def ready(self):
        """导入信号处理程序"""
        # 导入信号模块，确保信号被注册
        import storage.signals