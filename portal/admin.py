import json
from django.contrib import admin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import path
from .models import studentdata, NsqfElectronics, NsqfIT, Dlc, PlacementRecord
from import_export.admin import ImportExportModelAdmin


class StudentDataAdmin(ImportExportModelAdmin):
    list_display=["session",
    "roll_number" ,
    "name",
    "father_name",
    "mother_name",
    "dob",
    "gender",
    "qualifications",
    "address",
    "aadhaar",
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
    "fee_date",
    "trained",       
    "trained_date",    
    "certified",     
    "certified_date",  
    "placed"
      ]   
    search_fields = ["name", "aadhaar", "roll_number", "batch_code"]

admin.site.register(studentdata, StudentDataAdmin)
admin.site.register(NsqfIT)
admin.site.register(NsqfElectronics)
admin.site.register(Dlc)


class PlacementRecordAdmin(admin.ModelAdmin):
    list_display = [
        "student_name", "aadhaar", "course_name", "batch_code",
        "opportunity_type", "company", "job_title", "placed", "created_at",
    ]
    list_filter = ["placed", "opportunity_type", "center_name"]
    search_fields = ["student_name", "aadhaar", "company", "course_name"]
    autocomplete_fields = ["student"]
    list_select_related = ["student"]
    fieldsets = [
        (
            "Student Information",
            {
                "fields": [
                    "student",
                    "student_name",
                    "aadhaar",
                    "course_name",
                    "batch_code",
                    "center_name",
                ]
            },
        ),
        (
            "Placement & Company Details",
            {
                "fields": [
                    "opportunity_type",
                    "selection_status",
                    "offer_received",
                    "company",
                    "job_title",
                    "source",
                    "date_applied",
                    "joining_date",
                    "current_status",
                    "placed",
                ]
            },
        ),
    ]

    def save_model(self, request, obj, form, change):
        if obj.student:
            if not obj.student_name:
                obj.student_name = obj.student.name
            if not obj.aadhaar:
                obj.aadhaar = obj.student.roll_number or obj.student.aadhaar
            if not obj.course_name:
                obj.course_name = obj.student.course_name
            if not obj.batch_code:
                obj.batch_code = obj.student.batch_code
            if not obj.center_name:
                obj.center_name = obj.student.center_name
        super().save_model(request, obj, form, change)

    class Media:
        js = ("js/placement_admin.js",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "student-details/<int:student_id>/",
                self.admin_site.admin_view(self.student_details_view),
                name="placement-student-details",
            ),
            path(
                "search-students/",
                self.admin_site.admin_view(self.search_students_view),
                name="placement-search-students",
            ),
            path(
                "create-placement/",
                self.admin_site.admin_view(self.create_placement_view),
                name="placement-create",
            ),
        ]
        return custom_urls + urls

    def student_details_view(self, request, student_id):
        try:
            student = studentdata.objects.get(id=student_id)
            return JsonResponse({
                "name": student.name or "",
                "roll_number": student.roll_number or "",
                "course_name": student.course_name or "",
                "batch_code": student.batch_code or "",
                "center_name": student.center_name or "",
            })
        except studentdata.DoesNotExist:
            return JsonResponse({"error": "Student not found"}, status=404)

    def search_students_view(self, request):
        q = request.GET.get("q", "")
        students = studentdata.objects.filter(
            Q(name__icontains=q) | Q(roll_number__icontains=q) | Q(aadhaar__icontains=q)
        )[:20]
        results = [
            {
                "id": s.id,
                "text": f"{s.name} ({s.roll_number or s.aadhaar})",
                "name": s.name or "",
                "roll_number": s.roll_number or "",
                "course_name": s.course_name or "",
                "batch_code": s.batch_code or "",
                "center_name": s.center_name or "",
            }
            for s in students
        ]
        return JsonResponse({"results": results})

    def create_placement_view(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        student_id = data.get("student")
        student = studentdata.objects.filter(id=student_id).first() if student_id else None

        placed = data.get("placed") == "true" or data.get("offer_received") == "true"

        pr = PlacementRecord.objects.create(
            student=student,
            student_name=data.get("student_name", student.name if student else ""),
            aadhaar=data.get("aadhaar", student.roll_number if student else ""),
            course_name=data.get("course_name", student.course_name if student else ""),
            batch_code=data.get("batch_code", student.batch_code if student else ""),
            center_name=data.get("center_name", student.center_name if student else ""),
            opportunity_type=data.get("opportunity_type", ""),
            selection_status=data.get("selection_status", ""),
            offer_received=data.get("offer_received") == "true",
            company=data.get("company", ""),
            job_title=data.get("job_title", ""),
            source=data.get("source", ""),
            date_applied=data.get("date_applied", ""),
            joining_date=data.get("joining_date", ""),
            current_status=data.get("current_status", ""),
            placed=placed,
        )

        if student:
            student.placed = True
            student.save()

        return JsonResponse({"success": True, "id": pr.id})


admin.site.register(PlacementRecord, PlacementRecordAdmin)