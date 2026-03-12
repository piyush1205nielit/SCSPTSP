from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse
import pandas as pd
from django.shortcuts import render, redirect
from .forms import ExcelUploadForm, StudentDataForm
from .models import studentdata

# Create your views here.
def dashboard(request):
    return render(request,"dashboard.html")




def upload(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['file']

            # Read Excel into DataFrame
            df = pd.read_excel(excel_file)

            # Loop through each row and save using ModelForm
            for _, row in df.iterrows():
                data = {
                    'session': row.get('session'),
                    'name': row.get('name'),
                    'course_name': row.get('course_name'),
                    'course_hour': row.get('course_hour'),
                    'scheme': row.get('scheme'),
                    'mode': row.get('mode'),
                    'caste_category': row.get('caste_category'),
                    'center_name': row.get('center_name'),
                    'trained': row.get('trained', False),
                    'certified': row.get('certified', False),
                    'placed': row.get('placed', False),
                }
                StudentDataForm(data).save()

            return redirect('upload_excel')  # Redirect back or anywhere you want
    else:
        form = ExcelUploadForm()

    return render(request, 'upload.html', {'form': form})


def filter_data(request):
    query = request.GET.get("q")

    results = studentdata.objects.filter(name__icontains=query)

    data = list(results.values("id", "name"))

    return JsonResponse({"results": data})
