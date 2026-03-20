from django import forms
from .models import File, Folder

class FileUploadForm(forms.Form):
    """Form for uploading multiple files"""
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
        }),
        label='选择文件'
    )
    
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