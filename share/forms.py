from django import forms

class FileShareForm(forms.Form):
    """Form for creating file shares"""
    EXPIRY_CHOICES = [
        (1, '1小时'),
        (24, '24小时'),
        (168, '7天'),
        (720, '30天'),
        (None, '永久有效'),
    ]
    
    expires_hours = forms.ChoiceField(
        choices=EXPIRY_CHOICES,
        required=False,
        label='有效期',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    password = forms.CharField(
        max_length=100,
        required=False,
        label='访问密码',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '可选，设置后需要密码才能访问'
        })
    )
    
    def clean_expires_hours(self):
        expires_hours = self.cleaned_data.get('expires_hours')
        if expires_hours == '' or expires_hours is None:
            return None
        return int(expires_hours)