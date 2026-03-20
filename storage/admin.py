from django.contrib import admin
from .models import File, Folder

@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'parent', 'created_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('name', 'owner__username')
    raw_id_fields = ('owner', 'parent')

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('name', 'original_name', 'owner', 'folder', 'formatted_size', 'uploaded_at')
    list_filter = ('owner', 'file_type', 'uploaded_at')
    search_fields = ('name', 'original_name', 'owner__username')
    raw_id_fields = ('owner', 'folder')
    readonly_fields = ('size', 'file_type', 'uploaded_at', 'updated_at')
    
    def formatted_size(self, obj):
        return obj.formatted_size
    formatted_size.short_description = 'Size'