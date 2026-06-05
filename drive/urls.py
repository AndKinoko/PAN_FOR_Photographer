"""
URL Configuration for drive project.

The `urlpatterns` list routes URLs to views.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/storage/', permanent=False)),
    path('', include('accounts.urls')),
    path('storage/', include('storage.urls')),
    path('search/', include('search.urls')),
    path('share/', include('share.urls')),
]

# 静态文件（CSS/JS/图片等前端资源）通过 Django 提供
# 注意：媒体文件（用户上传的文件）不在此处提供，需要通过认证视图访问
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)