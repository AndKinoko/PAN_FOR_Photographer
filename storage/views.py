from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponseForbidden, StreamingHttpResponse, JsonResponse
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
import os
import re
import json
import shutil
import logging
import threading
from uuid import uuid4
from datetime import timedelta

from accounts.models import UserProfile, format_bytes
from .models import File, Folder, UploadSession
from .forms import FileUploadForm, FolderCreateForm

logger = logging.getLogger(__name__)

# 与旧表单上传保持一致的安全限制
BLOCKED_EXTS = {'.html', '.htm', '.svg', '.js', '.mjs'}
CHUNK_SIZE = getattr(settings, 'TRANSFER_CHUNK_SIZE', 5 * 1024 * 1024)
MAX_FILE_SIZE = getattr(settings, 'TRANSFER_MAX_FILE_SIZE', 10737418240)
# complete 临界区按用户串行：配额检查+建档原子化，并发完成不超额
_complete_guard = threading.Lock()
_complete_locks = {}


def _user_lock(user_id):
    with _complete_guard:
        lock = _complete_locks.get(user_id)
        if lock is None:
            lock = threading.Lock()
            _complete_locks[user_id] = lock
        return lock


def range_file_response(request, abs_path, filename, content_type=None, inline=False):
    """支持 Range 断点续传的文件响应；切片按 1MB 流式读，内存恒定。"""
    size = os.path.getsize(abs_path)
    start, end = 0, size - 1
    status = 200
    range_header = (request.META.get('HTTP_RANGE') or '').strip()
    m = re.match(r'bytes=(\d*)-(\d*)$', range_header)
    if m:
        s, e = m.groups()
        if s == '' and e != '':
            start = max(0, size - int(e))
        else:
            start = int(s) if s else 0
            end = int(e) if e and int(e) < size else size - 1
        if start >= size or start > end:
            resp = StreamingHttpResponse(status=416)
            resp['Content-Range'] = f'bytes */{size}'
            resp['Accept-Ranges'] = 'bytes'
            return resp
        status = 206

    length = end - start + 1

    def slicer(path=abs_path, offset=start, remaining=length):
        with open(path, 'rb') as f:
            f.seek(offset)
            while remaining > 0:
                data = f.read(min(1024 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    if status == 206:
        resp = StreamingHttpResponse(slicer(), status=206,
                                     content_type=content_type or 'application/octet-stream')
        resp['Content-Range'] = f'bytes {start}-{end}/{size}'
    else:
        resp = FileResponse(open(abs_path, 'rb'), content_type=content_type)
    resp['Content-Length'] = str(length)
    resp['Accept-Ranges'] = 'bytes'
    disp = 'inline' if inline else 'attachment'
    resp['Content-Disposition'] = f'{disp}; filename="{filename}"'
    return resp


def get_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def is_frozen(user):
    return get_profile(user).is_frozen


def frozen_response(request):
    messages.error(request, '账号已冻结，仅可登录预览，请联系管理员')
    return redirect('storage:file_list')

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
    """旧上传页：GET 跳转新版文件传输页，POST 保留兼容处理"""
    if is_frozen(request.user):
        return frozen_response(request)

    if request.method == 'GET':
        from django.urls import reverse
        base = reverse('storage:transfer')
        if folder_id:
            return redirect(f'{base}?folder={folder_id}')
        return redirect(base)

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

            # ─── 配额检查 ────────────────────────────────────────────────────
            profile = get_profile(request.user)
            if profile.quota_bytes:
                incoming = sum(f.size for f in files)
                usage = profile.usage_bytes()
                if usage + incoming > profile.quota_bytes:
                    messages.error(
                        request,
                        f'容量不足：已用 {format_bytes(usage)} / 配额 {format_bytes(profile.quota_bytes)}，'
                        f'本次需 {format_bytes(incoming)}，请联系管理员扩容'
                    )
                    if folder:
                        return redirect('storage:file_list', folder_id=folder.id)
                    return redirect('storage:file_list')
            # ─── 配额检查结束 ────────────────────────────────────────────────

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
    if is_frozen(request.user):
        return HttpResponseForbidden('账号已冻结，无法下载（仍可登录预览），请联系管理员')
    file = get_object_or_404(File, id=file_id, owner=request.user)

    if os.path.exists(file.file.path):
        return range_file_response(request, file.file.path, file.original_name)
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

    # 冻结账号：允许预览图/图片类预览，禁止原文件直链（等同下载）
    if is_frozen(request.user) and not is_preview:
        return HttpResponseForbidden('账号已冻结，无法下载（仍可登录预览），请联系管理员')
    
    if is_preview and file.preview and os.path.exists(file.preview.path):
        # 返回预览图（小 JPEG，保持原逻辑）
        response = FileResponse(file.preview.open('rb'))
        response['Content-Type'] = 'image/jpeg'
        return response
    elif is_preview:
        # 请求预览但预览不存在（如 RAW 预览生成失败）
        raise Http404("预览文件不存在")
    else:
        # 返回原始文件（内联展示，支持 Range 续传）
        return range_file_response(request, file.file.path, file.original_name, inline=True)

@login_required
def file_delete(request, file_id):
    """Delete a file"""
    if is_frozen(request.user):
        return frozen_response(request)
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
    if is_frozen(request.user):
        return frozen_response(request)
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
    if is_frozen(request.user):
        return frozen_response(request)
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


# ================= 文件传输中心 =================

@login_required
def transfer(request):
    """文件传输中心：分片上传队列 + Range 下载任务"""
    folder = None
    folder_id = request.GET.get('folder')
    if folder_id:
        try:
            folder = Folder.objects.get(id=int(folder_id), owner=request.user)
        except (Folder.DoesNotExist, ValueError):
            folder = None

    folders = sorted(
        Folder.objects.filter(owner=request.user),
        key=lambda f: f.path.lower(),
    )
    profile = get_profile(request.user)
    usage = profile.usage_bytes()
    context = {
        'current_folder': folder,
        'folders': folders,
        'quota_usage': usage,
        'quota_usage_display': format_bytes(usage),
        'quota_display': format_bytes(profile.quota_bytes),
        'chunk_size': CHUNK_SIZE,
        'max_file_size': MAX_FILE_SIZE,
        'auto_download_id': request.GET.get('download', ''),
    }
    return render(request, 'storage/transfer.html', context)


@login_required
def api_filemeta(request):
    """下载任务元信息：自己的文件才返回，供 ?download=ID 自动加入任务。"""
    try:
        file_id = int(request.GET.get('id', ''))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'id 非法'}, status=400)
    try:
        f = File.objects.get(id=file_id, owner=request.user)
    except File.DoesNotExist:
        return JsonResponse({'error': '文件不存在或无权访问'}, status=404)
    return JsonResponse({'id': f.id, 'name': f.name, 'size': f.size})


@login_required
def api_quota(request):
    profile = get_profile(request.user)
    usage = profile.usage_bytes()
    return JsonResponse({
        'usage': usage,
        'usage_display': format_bytes(usage),
        'quota': profile.quota_bytes,
        'quota_display': format_bytes(profile.quota_bytes),
    })


def _purge_stale_sessions():
    """清理超过保留时长的未完成会话（含落盘分片），防磁盘膨胀。"""
    stale_hours = getattr(settings, 'TRANSFER_STALE_HOURS', 24)
    cutoff = timezone.now() - timedelta(hours=stale_hours)
    for s in UploadSession.objects.filter(status=UploadSession.STATUS_UPLOADING,
                                          updated_at__lt=cutoff):
        s.cleanup()
        s.status = UploadSession.STATUS_CANCELLED
        s.save(update_fields=['status'])


def _check_uploadable(user, filename, total_size, folder):
    """分片上传通用校验，返回 (ok, error_msg, status_code)。"""
    if not filename:
        return False, '缺少文件名', 400
    if total_size <= 0:
        return False, '文件大小异常', 400
    if total_size > MAX_FILE_SIZE:
        return False, f'文件超过单文件上限 {format_bytes(MAX_FILE_SIZE)}', 413
    ext = os.path.splitext(filename)[1].lower()
    if ext in BLOCKED_EXTS:
        return False, f'文件类型 "{ext}" 不允许上传（存在安全风险）', 400
    if File.objects.filter(owner=user, folder=folder,
                           original_name__iexact=filename).exists():
        return False, f'“{filename}”与目标文件夹中的文件重名', 409
    profile = get_profile(user)
    if profile.quota_bytes and profile.usage_bytes() + total_size > profile.quota_bytes:
        return False, (f'容量不足：已用 {format_bytes(profile.usage_bytes())} / '
                       f'配额 {format_bytes(profile.quota_bytes)}'), 413
    return True, '', 200


@login_required
def api_upload_init(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)
    if is_frozen(request.user):
        return JsonResponse({'error': '账号已冻结，仅可登录预览'}, status=403)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求体不是合法 JSON'}, status=400)

    filename = (data.get('filename') or '').strip()
    try:
        total_size = int(data.get('total_size') or 0)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'total_size 非法'}, status=400)
    folder = None
    if data.get('folder_id'):
        try:
            folder = Folder.objects.get(id=int(data['folder_id']), owner=request.user)
        except (Folder.DoesNotExist, ValueError):
            return JsonResponse({'error': '目标文件夹不存在'}, status=404)

    ok, err, code = _check_uploadable(request.user, filename, total_size, folder)
    if not ok:
        return JsonResponse({'error': err}, status=code)

    _purge_stale_sessions()

    # 断点续传：同用户同目录同名同大小的未完成会话直接复用
    session = (UploadSession.objects
               .filter(owner=request.user, folder=folder, original_name=filename,
                       total_size=total_size, status=UploadSession.STATUS_UPLOADING)
               .order_by('-updated_at').first())
    if session is None:
        total_chunks = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        session = UploadSession.objects.create(
            session_id=uuid4().hex,
            owner=request.user, folder=folder,
            original_name=filename, total_size=total_size,
            chunk_size=CHUNK_SIZE, total_chunks=total_chunks,
        )
    else:
        session.save(update_fields=['updated_at'])

    return JsonResponse({
        'session_id': session.session_id,
        'chunk_size': session.chunk_size,
        'total_chunks': session.total_chunks,
        'received': session.received_indices(),
    })


@login_required
def api_upload_chunk(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)
    if is_frozen(request.user):
        return JsonResponse({'error': '账号已冻结，仅可登录预览'}, status=403)
    session = get_object_or_404(UploadSession, session_id=request.POST.get('session_id'),
                                owner=request.user,
                                status=UploadSession.STATUS_UPLOADING)
    try:
        index = int(request.POST.get('index'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'index 非法'}, status=400)
    if not 0 <= index < session.total_chunks:
        return JsonResponse({'error': 'index 越界'}, status=400)
    uploaded = request.FILES.get('chunk')
    if uploaded is None:
        return JsonResponse({'error': '缺少分片数据'}, status=400)
    if uploaded.size > session.chunk_size + 1024 * 1024:
        return JsonResponse({'error': '分片过大'}, status=400)

    os.makedirs(session.temp_dir(), exist_ok=True)
    # 流式落盘，内存占用≈单次 read 块（默认 256KB）
    with open(session.chunk_path(index), 'wb') as out:
        for piece in uploaded.chunks():
            out.write(piece)
    session.save(update_fields=['updated_at'])
    return JsonResponse({'received': session.received_indices(),
                         'done': session.is_complete()})


@login_required
def api_upload_complete(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)
    if is_frozen(request.user):
        return JsonResponse({'error': '账号已冻结，仅可登录预览'}, status=403)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求体不是合法 JSON'}, status=400)
    session = get_object_or_404(UploadSession, session_id=data.get('session_id'),
                                owner=request.user,
                                status=UploadSession.STATUS_UPLOADING)

    # 临界区按用户串行：并发完成时配额检查+建档原子化
    with _user_lock(request.user.id):
        if not session.is_complete():
            missing = session.total_chunks - len(session.received_indices())
            return JsonResponse({'error': f'分片不完整，还缺 {missing} 片'}, status=400)
        ok, err, code = _check_uploadable(request.user, session.original_name,
                                          session.total_size, session.folder)
        if not ok:
            return JsonResponse({'error': err}, status=code)

        ext = os.path.splitext(session.original_name)[1].lower()
        rel_path = f'user_{request.user.id}/{uuid4().hex}{ext}'
        abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        # 流式合并（1MB 缓冲），不整文件进内存
        with open(abs_path, 'wb') as out:
            for i in range(session.total_chunks):
                with open(session.chunk_path(i), 'rb') as part:
                    shutil.copyfileobj(part, out, 1024 * 1024)
        if os.path.getsize(abs_path) != session.total_size:
            os.unlink(abs_path)
            return JsonResponse({'error': '合并后大小校验失败，请重试'}, status=500)

        file_instance = File(
            owner=request.user, folder=session.folder,
            file=rel_path, original_name=session.original_name,
            name=session.original_name, size=session.total_size,
        )
        file_instance.save()  # 预览生成在内部串行锁中执行
        session.status = UploadSession.STATUS_DONE
        session.save(update_fields=['status'])
        session.cleanup()

    return JsonResponse({'file_id': file_instance.id, 'name': file_instance.name,
                         'size': file_instance.size,
                         'size_display': file_instance.formatted_size})


@login_required
def api_upload_cancel(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'method not allowed'}, status=405)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': '请求体不是合法 JSON'}, status=400)
    session = get_object_or_404(UploadSession, session_id=data.get('session_id'),
                                owner=request.user,
                                status=UploadSession.STATUS_UPLOADING)
    session.cleanup()
    session.status = UploadSession.STATUS_CANCELLED
    session.save(update_fields=['status'])
    return JsonResponse({'ok': True})