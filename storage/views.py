from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404
from django.db.models import Q
import os
import logging

from .models import File, Folder
from .forms import FileUploadForm, FolderCreateForm

logger = logging.getLogger(__name__)

@login_required
def file_list(request, folder_id=None):
    """Display files and folders for the current user"""
    folder = None
    if folder_id:
        folder = get_object_or_404(Folder, id=folder_id, owner=request.user)
    
    # Get user's folders
    folders = Folder.objects.filter(owner=request.user, parent=folder).order_by('name')
    
    # Get user's files
    files = File.objects.filter(owner=request.user, folder=folder).order_by('-uploaded_at')
    
    # Get parent folders for breadcrumb
    breadcrumbs = []
    current = folder
    while current:
        breadcrumbs.insert(0, current)
        current = current.parent
    
    context = {
        'folders': folders,
        'files': files,
        'current_folder': folder,
        'breadcrumbs': breadcrumbs,
    }
    return render(request, 'storage/file_list.html', context)

@login_required
def file_upload(request, folder_id=None):
    """Handle file upload"""
    folder = None
    if folder_id:
        folder = get_object_or_404(Folder, id=folder_id, owner=request.user)
    
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES, user=request.user, folder=folder)
        files = request.FILES.getlist('file')
        
        logger.info(f"File upload request by user {request.user.id}, folder_id: {folder_id}")
        logger.info(f"Number of files in request: {len(files)}")
        
        # Validate form
        if form.is_valid():
            logger.info("Form validation passed")
            
            if not files:
                logger.warning("No files selected for upload")
                messages.error(request, '请选择要上传的文件')
                return redirect('storage:file_upload', folder_id=folder_id) if folder_id else redirect('storage:file_upload')
            
            # ─── 文件名重复检查 ────────────────────────────────────────────
            uploaded_names = [f.name for f in files]
            existing_files = File.objects.filter(owner=request.user, folder=folder)
            existing_names = set(
                existing_files.values_list('original_name', flat=True)
            )
            
            # 不区分大小写比较
            normalized_existing = {name.lower() for name in existing_names}
            duplicates = [
                name for name in uploaded_names
                if name.lower() in normalized_existing
            ]
            
            if duplicates:
                duplicate_list = '\n'.join(f'  • {name}' for name in duplicates)
                logger.warning(
                    f"Duplicate filenames detected for user {request.user.id}: "
                    f"{' ,'.join(duplicates)}"
                )
                msg = (
                    f'以下 {len(duplicates)} 个文件与目标文件夹中的文件重名，上传已取消：\n'
                    f'{duplicate_list}'
                )
                messages.error(request, msg)
                if folder:
                    return redirect('storage:file_list', folder_id=folder.id)
                else:
                    return redirect('storage:file_list')
            # ─── 重复检查结束 ────────────────────────────────────────────────
            
            if files:
                successful_uploads = 0
                failed_uploads = 0
                
                for uploaded_file in files:
                    logger.info(f"Processing file: {uploaded_file.name}, size: {uploaded_file.size}")
                    
                    # 检查文件类型安全性
                    ext = os.path.splitext(uploaded_file.name)[1].lower()
                    blocked_exts = {'.html', '.htm', '.svg', '.js', '.mjs'}
                    if ext in blocked_exts:
                        error_msg = f'文件 {uploaded_file.name} 类型 "{ext}" 不允许上传（存在安全风险）'
                        logger.warning(error_msg)
                        messages.error(request, error_msg)
                        failed_uploads += 1
                        continue
                    
                    # Check file size (effectively unlimited - 10GB limit for safety)
                    MAX_FILE_SIZE = 10737418240  # 10GB - effectively unlimited
                    if uploaded_file.size > MAX_FILE_SIZE:
                        error_msg = f'文件 {uploaded_file.name} 大小超过限制 (最大 10GB)'
                        logger.warning(error_msg)
                        messages.error(request, error_msg)
                        failed_uploads += 1
                        continue
                    
                    file_instance = File(
                        owner=request.user,
                        folder=folder,
                        file=uploaded_file,
                        original_name=uploaded_file.name,
                        name=uploaded_file.name,
                    )
                    try:
                        file_instance.save()
                        logger.info(f"File saved successfully: {file_instance.id}")
                        successful_uploads += 1
                    except Exception as e:
                        logger.error(f"Error saving file {uploaded_file.name}: {str(e)}")
                        messages.error(request, f'文件 {uploaded_file.name} 上传失败: {str(e)}')
                        failed_uploads += 1
                
                if successful_uploads > 0:
                    messages.success(request, f'成功上传 {successful_uploads} 个文件{f"，{failed_uploads} 个文件失败" if failed_uploads > 0 else ""}')
                else:
                    messages.error(request, '没有文件上传成功')
                
                if folder:
                    return redirect('storage:file_list', folder_id=folder.id)
                else:
                    return redirect('storage:file_list')
            else:
                logger.warning("No files selected for upload")
                messages.error(request, '请选择要上传的文件')
        else:
            logger.warning(f"Form validation failed: {form.errors}")
            messages.error(request, '表单验证失败，请检查输入')
    else:
        form = FileUploadForm(user=request.user, folder=folder)
    
    context = {
        'form': form,
        'current_folder': folder,
    }
    return render(request, 'storage/file_upload.html', context)

@login_required
def file_download(request, file_id):
    """Download a file"""
    file = get_object_or_404(File, id=file_id, owner=request.user)
    
    if os.path.exists(file.file.path):
        response = FileResponse(file.file.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{file.original_name}"'
        return response
    else:
        raise Http404("文件不存在")

@login_required
def serve_media(request, file_id):
    """受保护的媒体文件访问 - 需要登录认证后才能预览文件"""
    file = get_object_or_404(File, id=file_id, owner=request.user)
    
    if not os.path.exists(file.file.path):
        raise Http404("文件不存在")
    
    # 判断是否为预览请求（带 preview 参数）
    is_preview = request.GET.get('preview', '') == '1'
    
    if is_preview and file.preview and os.path.exists(file.preview.path):
        # 返回预览图
        response = FileResponse(file.preview.open('rb'))
        content_type = 'image/jpeg'
    elif is_preview:
        # 请求预览但预览不存在（如 RAW 预览生成失败）
        raise Http404("预览文件不存在")
    else:
        # 返回原始文件（内联展示）
        response = FileResponse(file.file.open('rb'))
        content_type = None  # 让 Django 自动检测
    
    if content_type:
        response['Content-Type'] = content_type
    
    # 对内联内容不设置 Content-Disposition，允许浏览器直接展示
    if not is_preview:
        response['Content-Disposition'] = f'inline; filename="{file.original_name}"'
    
    return response

@login_required
def file_delete(request, file_id):
    """Delete a file"""
    file = get_object_or_404(File, id=file_id, owner=request.user)
    folder_id = file.folder.id if file.folder else None
    
    if request.method == 'POST':
        file.delete()
        messages.success(request, '文件已删除')
        if folder_id:
            return redirect('storage:file_list', folder_id=folder_id)
        else:
            return redirect('storage:file_list')
    
    context = {'file': file}
    return render(request, 'storage/file_delete.html', context)

@login_required
def folder_create(request, parent_id=None):
    """Create a new folder"""
    parent = None
    if parent_id:
        parent = get_object_or_404(Folder, id=parent_id, owner=request.user)
    
    if request.method == 'POST':
        form = FolderCreateForm(request.POST, user=request.user)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.owner = request.user
            folder.save()
            messages.success(request, '文件夹创建成功')
            if parent:
                return redirect('storage:file_list', folder_id=parent.id)
            else:
                return redirect('storage:file_list')
    else:
        form = FolderCreateForm(user=request.user, initial={'parent': parent})
    
    context = {
        'form': form,
        'parent_folder': parent,
    }
    return render(request, 'storage/folder_create.html', context)

@login_required
def folder_delete(request, folder_id):
    """Delete a folder"""
    folder = get_object_or_404(Folder, id=folder_id, owner=request.user)
    parent_id = folder.parent.id if folder.parent else None
    
    if request.method == 'POST':
        # Delete all files in the folder first
        for file in folder.files.all():
            file.file.delete()
            file.delete()
        
        # Delete subfolders recursively
        def delete_folder_recursive(f):
            for subfolder in f.subfolders.all():
                delete_folder_recursive(subfolder)
            f.delete()
        
        delete_folder_recursive(folder)
        messages.success(request, '文件夹已删除')
        if parent_id:
            return redirect('storage:file_list', folder_id=parent_id)
        else:
            return redirect('storage:file_list')
    
    context = {'folder': folder}
    return render(request, 'storage/folder_delete.html', context)