from django.contrib import admin
from .models import studentdata
from import_export.admin import ImportExportModelAdmin
# Register your models here.


class StudentDataAdmin(ImportExportModelAdmin):
    list_display=["session",
    "roll_number" ,
    "course_name",    
    "course_hour",  
    "course_category",
    "scheme",       
    "nsqf",     
    "mode",         
    "caste_category", 
    "center_name",    
    "fee",         
    "claimable_amount",
    "trained",       
    "trained_date",    
    "certified",     
    "certified_date",  
    "placed"
      ]   

admin.site.register(studentdata,StudentDataAdmin)