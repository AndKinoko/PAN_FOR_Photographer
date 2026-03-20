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
    
    # Folder operations
    path('folder/create/', views.folder_create, name='folder_create'),
    path('folder/create/<int:parent_id>/', views.folder_create, name='folder_create'),
    path('folder/delete/<int:folder_id>/', views.folder_delete, name='folder_delete'),
]