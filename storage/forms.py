from django import forms
from django.core.exceptions import ValidationError
from .models import File, Folder
import os

class FileUploadForm(forms.Form):
    """Form for uploading multiple files"""
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
        }),
        label='选择文件'
    )
    
    # 禁止上传的可执行/脚本文件类型（防止 XSS 和恶意内容分发）
    BLOCKED_EXTENSIONS = {
        '.html', '.htm', '.svg', '.js', '.mjs',  # XSS 向量
    }

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')
        if not uploaded_file:
            return uploaded_file
        
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        
        # 拦截危险文件类型
        if ext in self.BLOCKED_EXTENSIONS:
            raise ValidationError(
                f'文件类型 "{ext}" 不允许上传（存在安全风险）'
            )
        
        return uploaded_file
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.folder = kwargs.pop('folder', None)
        super().__init__(*args, **kwargs)

class FolderCreateForm(forms.ModelForm):
    class Meta:
        model = Folder
        fields = ['name', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '文件夹名称'}),
            'parent': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Only show folders belonging to the current user
        if self.user:
            self.fields['parent'].queryset = Folder.objects.filter(owner=self.user)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user:
            instance.owner = self.user
        if commit:
            instance.save()
        return instance