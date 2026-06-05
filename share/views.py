from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404
from django.utils import timezone
import os

from storage.models import File
from .models import FileShare
from .forms import FileShareForm

@login_required
def create_share(request, file_id):
    """Create a file share link"""
    file = get_object_or_404(File, id=file_id, owner=request.user)
    
    if request.method == 'POST':
        form = FileShareForm(request.POST)
        if form.is_valid():
            expires_hours = form.cleaned_data.get('expires_hours')
            password = form.cleaned_data.get('password', '')
            
            share = FileShare.create_share(
                file=file,
                owner=request.user,
                expires_hours=expires_hours,
                password=password
            )
            
            messages.success(request, '文件分享链接创建成功！')
            return redirect('share:share_detail', share_id=share.id)
    else:
        form = FileShareForm()
    
    context = {
        'form': form,
        'file': file,
    }
    return render(request, 'share/create_share.html', context)

@login_required
def share_detail(request, share_id):
    """View share details"""
    share = get_object_or_404(FileShare, id=share_id, owner=request.user)
    
    context = {
        'share': share,
        'file': share.file,
        'full_url': request.build_absolute_uri(share.share_url),
    }
    return render(request, 'share/share_detail.html', context)

@login_required
def my_shares(request):
    """List user's file shares"""
    shares = FileShare.objects.filter(owner=request.user).order_by('-created_at')
    
    context = {
        'shares': shares,
    }
    return render(request, 'share/my_shares.html', context)

@login_required
def delete_share(request, share_id):
    """Delete a file share"""
    share = get_object_or_404(FileShare, id=share_id, owner=request.user)
    
    if request.method == 'POST':
        share.delete()
        messages.success(request, '分享链接已删除')
        return redirect('share:my_shares')
    
    context = {'share': share}
    return render(request, 'share/delete_share.html', context)

def share_access(request, share_id):
    """Access a shared file"""
    share = get_object_or_404(FileShare, id=share_id)
    
    # Check if share is valid
    if not share.is_valid:
        return render(request, 'share/share_expired.html', {'share': share})
    
    # Check password if set
    if share.password:
        if request.method == 'POST':
            entered_password = request.POST.get('password', '')
            if share.verify_password(entered_password):
                request.session[f'share_access_{share_id}'] = True
                return redirect('share:share_download', share_id=share.id)
            else:
                messages.error(request, '密码错误')
        else:
            # Check if already authenticated
            if not request.session.get(f'share_access_{share_id}'):
                return render(request, 'share/share_password.html', {'share': share})
    else:
        # No password required
        request.session[f'share_access_{share_id}'] = True
    
    return redirect('share:share_download', share_id=share.id)

def share_download(request, share_id):
    """Download a shared file"""
    share = get_object_or_404(FileShare, id=share_id)
    
    # Check access
    if not share.is_valid:
        return render(request, 'share/share_expired.html', {'share': share})
    
    if share.password and not request.session.get(f'share_access_{share_id}'):
        return redirect('share:share_access', share_id=share.id)
    
    # Increment download count
    share.increment_download()
    
    # Serve the file
    if os.path.exists(share.file.file.path):
        response = FileResponse(share.file.file.open('rb'))
        response['Content-Disposition'] = f'attachment; filename="{share.file.original_name}"'
        return response
    else:
        raise Http404("文件不存在")