from django import forms
from .models import studentdata
class studentform(forms.ModelForm):
    class Meta:
        model=studentdata
        feild="__all__"