from django.urls import path
from . import views

app_name = 'share'

urlpatterns = [
    # User share management
    path('create/<int:file_id>/', views.create_share, name='create_share'),
    path('detail/<uuid:share_id>/', views.share_detail, name='share_detail'),
    path('my-shares/', views.my_shares, name='my_shares'),
    path('delete/<uuid:share_id>/', views.delete_share, name='delete_share'),
    
    # Public access
    path('<uuid:share_id>/', views.share_access, name='share_access'),
    path('<uuid:share_id>/download/', views.share_download, name='share_download'),
]