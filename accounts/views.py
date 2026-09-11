from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count

from storage.models import File
from .models import UserProfile, format_bytes

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


def register(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, '注册成功！欢迎使用局域网网盘。')
            return redirect('storage:file_list')
    else:
        form = UserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})


@staff_required
def user_management(request):
    """管理员：用户列表、冻结/解冻、配额、删除用户、设为/取消管理员。"""
    if request.method == 'POST':
        action = request.POST.get('action')
        target = get_object_or_404(User, id=request.POST.get('user_id'))
        profile, _ = UserProfile.objects.get_or_create(user=target)

        if target == request.user and action in ('toggle_freeze', 'delete_user', 'toggle_staff'):
            messages.error(request, '不能对自己的账号执行该操作')
            return redirect('accounts:user_management')

        if action == 'toggle_freeze':
            profile.is_frozen = not profile.is_frozen
            profile.save()
            messages.success(request, f'已{"冻结" if profile.is_frozen else "解冻"}用户 {target.username}')
        elif action == 'set_quota':
            raw = (request.POST.get('quota_gb') or '').strip()
            if raw == '':
                profile.quota_bytes = None
            else:
                try:
                    gb = float(raw)
                    if gb < 0:
                        raise ValueError
                    profile.quota_bytes = None if gb == 0 else int(gb * 1024 ** 3)
                except ValueError:
                    messages.error(request, '配额必须是数字（GB，0 表示不限额，留空也是不限额）')
                    return redirect('accounts:user_management')
            profile.save()
            messages.success(request, f'用户 {target.username} 配额已设为 {format_bytes(profile.quota_bytes)}')
        elif action == 'toggle_staff':
            if target.is_superuser:
                messages.error(request, '不能修改超级管理员的管理员身份')
            else:
                target.is_staff = not target.is_staff
                target.save()
                messages.success(request, f'用户 {target.username} 已{"设为" if target.is_staff else "取消"}管理员')
        elif action == 'delete_user':
            if target.is_superuser:
                messages.error(request, '不能删除超级管理员')
            else:
                username = target.username
                target.delete()
                messages.success(request, f'已删除用户 {username} 及其全部文件')
        else:
            messages.error(request, '未知操作')
        return redirect('accounts:user_management')

    users = User.objects.all().order_by('username').prefetch_related('profile')
    rows = []
    for u in users:
        profile, _ = UserProfile.objects.get_or_create(user=u)
        agg = File.objects.filter(owner=u).aggregate(size=Sum('size'), n=Count('id'))
        rows.append({
            'user': u,
            'profile': profile,
            'usage': int(agg['size'] or 0),
            'usage_display': format_bytes(agg['size'] or 0),
            'quota_display': format_bytes(profile.quota_bytes),
            'file_count': agg['n'] or 0,
        })

    total_files = File.objects.aggregate(size=Sum('size'), n=Count('id'))
    context = {
        'rows': rows,
        'stat_users': users.count(),
        'stat_frozen': UserProfile.objects.filter(is_frozen=True).count(),
        'stat_files': total_files['n'] or 0,
        'stat_size': format_bytes(total_files['size'] or 0),
    }
    return render(request, 'accounts/user_management.html', context)