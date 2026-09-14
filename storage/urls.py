from django.urls import path
from . import views

app_name = 'storage'

urlpatterns = [
    # File operations
    path('', views.file_list, name='file_list'),
    path('folder/<int:folder_id>/', views.file_list, name='file_list'),
    path('upload/', views.file_upload, name='file_upload'),
    path('upload/folder/<int:folder_id>/', views.file_upload, name='file_upload'),
    path('download/<int:file_id>/', views.file_download, name='file_download'),
    path('delete/<int:file_id>/', views.file_delete, name='file_delete'),
    path('media/<int:file_id>/', views.serve_media, name='serve_media'),
    
    # Folder operations
    path('folder/create/', views.folder_create, name='folder_create'),
    path('folder/create/<int:parent_id>/', views.folder_create, name='folder_create'),
    path('folder/delete/<int:folder_id>/', views.folder_delete, name='folder_delete'),

    # Transfer center
    path('transfer/', views.transfer, name='transfer'),
    path('api/quota/', views.api_quota, name='api_quota'),
    path('api/filemeta/', views.api_filemeta, name='api_filemeta'),
    path('api/upload/init/', views.api_upload_init, name='api_upload_init'),
    path('api/upload/chunk/', views.api_upload_chunk, name='api_upload_chunk'),
    path('api/upload/complete/', views.api_upload_complete, name='api_upload_complete'),
    path('api/upload/cancel/', views.api_upload_cancel, name='api_upload_cancel'),
]