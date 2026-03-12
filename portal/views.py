from django.shortcuts import render
from django.http import HttpResponse
from django.http import JsonResponse


# Create your views here.
def dashboard(request):
    return render(request,"dashboard.html")

def upload(request):
    return render(request,"upload.html")


from django.http import JsonResponse
from .models import studentdata

from django.http import JsonResponse
from .models import studentdata

def filter_students(request):

    center = request.GET.get("center")
    mode = request.GET.get("mode")
    caste = request.GET.get("caste")

    students = studentdata.objects.all()

    if center:
        students = students.filter(center_name=center)

    if mode:
        students = students.filter(mode=mode)

    if caste:
        students = students.filter(caste_category=caste)
    

    data = list(students.values(
        "name",
        "course_name",
        "center_name",
        "mode",
        "caste_category",
        "trained",
        "certified",
        "placed"
    ))

    return JsonResponse({"results":data})