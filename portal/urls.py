from django.contrib import admin
from django.urls import path
from portal import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('',views.dashboard,name="dashboard"),
    path("upload/",views.upload,name="upload"),
    path("filter-students/", views.filter_students, name="filter_students"),
    path('download/', views.download, name='download'),
    path('api/download-data/', views.api_download_data, name='api_download_data'),
    path('update-student/<int:student_id>/', views.update_student, name='update_student'),
    path("input_student/",views.inputView,name="input")
]