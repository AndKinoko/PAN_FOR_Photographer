from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages

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