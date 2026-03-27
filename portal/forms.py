from django import forms
from .models import studentdata
from datetime import datetime

# ModelForm for studentdata
from django import forms
from .models import studentdata

class StudentDataForm(forms.ModelForm):
    class Meta:
        model = studentdata
        fields = [
            "session", "roll_number", "name", "course_name", 
            "course_hour", "scheme", "nsqf", "mode", 
            "caste_category", "center_name", "fee", 
            "trained", "certified", "placed"
        ]
        
        widgets = {
            # Date and Text inputs
            "session": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "roll_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter Roll Number"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full Name"}),
            "course_name": forms.TextInput(attrs={"class": "form-control","placeholder": "Enter course name"}),
            "course_hour": forms.NumberInput(attrs={"class": "form-control","placeholder": "Enter course hours"}),
            "scheme": forms.TextInput(attrs={"class": "form-control","placeholder": "Enter Scheme"}),
            "nsqf": forms.TextInput(attrs={"class": "form-control","placeholder": "Enter NSQF"}),
            "fee": forms.NumberInput(attrs={"class": "form-control","placeholder": "Enter FEE"}),

            # Choice Fields (Dropdowns)
            "mode": forms.Select(attrs={"class": "form-select"}),
            "caste_category": forms.Select(attrs={"class": "form-select"}),
            "center_name": forms.Select(attrs={"class": "form-select"}),

            # Boolean Fields (Checkboxes)
            "trained": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "certified": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "placed": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

# Simple form to upload Excel
class ExcelUploadForm(forms.Form):
    # Generate years from 2020 to current year + 1
    current_year = datetime.now().year
    YEAR_CHOICES = [(str(year), str(year)) for year in range(2020, current_year + 2)]
    
    SESSION_CHOICES = [
        ('January', 'January'),
        ('February', 'February'),
        ('March', 'March'),
        ('April', 'April'),
        ('May', 'May'),
        ('June', 'June'),
        ('July', 'July'),
        ('August', 'August'),
        ('September', 'September'),
        ('October', 'October'),
        ('November', 'November'),
        ('December', 'December'),
    ]
    
    year = forms.ChoiceField(choices=YEAR_CHOICES, required=True, widget=forms.Select(attrs={'class': 'filter-select'}))
    session = forms.ChoiceField(choices=SESSION_CHOICES, required=True, widget=forms.Select(attrs={'class': 'filter-select'}))
    file = forms.FileField(widget=forms.FileInput(attrs={'class': 'file-input'}))