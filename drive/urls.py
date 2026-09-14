"""
URL Configuration for drive project.

The `urlpatterns` list routes URLs to views.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.views.static import serve as static_serve
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

# 本项目 DEBUG=False 但用 runserver 直接服务（局域网单机场景），
# 传输中心 JS 放在 static/ 源码目录，需显式提供，否则 {% static %} 会 404。
# 注意：static() 辅助函数在 DEBUG=False 时返回空列表，此处必须手写路由。
# 生产部署请改用 collectstatic + 前置服务器，并删除下面一段。
import os as _os
_static_src = _os.path.join(settings.BASE_DIR, 'static')
if _os.path.isdir(_static_src):
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', static_serve,
                {'document_root': _static_src}),
    ]