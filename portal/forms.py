from django import forms
from .models import studentdata
from django import forms
from .models import studentdata

# ModelForm for studentdata
class StudentDataForm(forms.ModelForm):
    class Meta:
        model = studentdata
        fields = '__all__'

# Simple form to upload Excel
class ExcelUploadForm(forms.Form):
    file = forms.FileField()