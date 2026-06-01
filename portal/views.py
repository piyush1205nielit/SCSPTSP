"""
Corrected upload view and supporting helpers.
Quarterly filtering now works based on trained_date and certified_date, not session.
"""

import json
import re
import traceback
from datetime import datetime
from decimal import Decimal
from statistics import mode

import openpyxl
from django.contrib import messages
from django.contrib.admin import options
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from openpyxl.styles import Font, PatternFill

from .forms import ExcelUploadForm, StudentDataForm
from .models import Dlc, NsqfElectronics, NsqfIT, UserProfile, studentdata

MONTH_MAP = {
    m: i
    for i, m in enumerate(
        [
            "JAN",
            "FEB",
            "MAR",
            "APR",
            "MAY",
            "JUN",
            "JUL",
            "AUG",
            "SEP",
            "OCT",
            "NOV",
            "DEC",
        ],
        1,
    )
}

SORTABLE_FIELDS = {
    "roll_number",
    "batch_code",
    "name",
    "course_name",
    "father_name",
    "mother_name",
    "dob",
    "gender",
    "address",
    "qualifications",
    "aadhaar",
    "scheme",
    "nsqf",
    "course_hour",
    "course_category",
    "center_name",
    "mode",
    "caste_category",
    "fee",
    "claimable_amount",
    "fee_date",
    "trained",
    "certified",
    "placed",
    "session",
    "claimed",
}

CENTERS = ["inderlok", "janakpuri", "karkardooma"]


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ["true", "yes", "1"]


def parse_date(value):
    """Return a date object or None. Accepts openpyxl date/datetime, or common string formats."""
    if not value:
        return None
    # openpyxl may give datetime/date objects
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            pass
    val_str = str(value).strip()
    # try multiple formats
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(val_str, fmt).date()
        except Exception:
            continue
    # fallback: None
    return None


def format_session_date(value):
    """Return MON-YYYY (e.g. JAN-2024) or empty string."""
    if not value:
        return ""
    # If it's a date/datetime, convert to MON-YYYY
    if hasattr(value, "strftime"):
        return value.strftime("%b-%Y").upper()
    # If it's already a string like JAN-2024 or Jan-2024 or 2024-01, normalize
    s = str(value).strip()
    # If looks like e.g. '2024-01' convert to 'JAN-2024'
    m = re.match(r"^(\d{4})[-/](\d{1,2})$", s)
    if m:
        year = m.group(1)
        month_no = int(m.group(2))
        # reverse lookup month abbrev
        month_abbr = (
            list(MONTH_MAP.keys())[month_no - 1] if 1 <= month_no <= 12 else None
        )
        if month_abbr:
            return f"{month_abbr}-{year}"
    # If already MON-YYYY (or similar), upper and normalize hyphen
    s2 = s.replace(" ", "-").replace("/", "-").upper()
    return s2


def quarter_from_date(date_str):
    if not date_str:
        return None, None
    try:
        month_str, year_str = date_str.upper().split("-")[:2]
        month = MONTH_MAP.get(month_str)
        return (f"Q{(month - 1) // 3 + 1}" if month else None), year_str
    except Exception:
        return None, None


def apply_filters(params, user=None):
    """
    CRITICAL FIX: Quarterly filtering now checks trained_date and certified_date.
    If filtering by Q1 and student was trained in Q1 but certified in Q2,
    the student appears as TRAINED (not certified) when Q1 is selected.
    When Q2 is selected, the student appears as CERTIFIED (not trained).

    Center-restricted users (non-superuser) can only see their assigned center.
    Django superusers (the global admin) see all centers.
    """
    qs = studentdata.objects.all()

    # Enforce center restriction for non-superuser users
    if user and not user.is_superuser:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.center_name:
            qs = qs.filter(center_name=profile.center_name)

    center = params.get("center")
    if center:
        qs = qs.filter(center_name=center)

    mode = params.get("mode")
    if mode:
        qs = qs.filter(mode=mode)

    caste = params.get("caste")
    if caste:
        qs = qs.filter(caste_category=caste)

    trained = params.get("trained")
    if trained:
        if trained == "or":
            qs = qs.filter(Q(trained=True) | Q(certified=True))
        else:
            qs = qs.filter(trained=parse_bool(trained))

    certified = params.get("certified")
    if certified:
        qs = qs.filter(certified=parse_bool(certified))

    placed = params.get("placed")
    if placed:
        qs = qs.filter(placed=parse_bool(placed))

    claimed = params.get("claimed")
    if claimed:
        qs = qs.filter(claimed=parse_bool(claimed))

    scheme = params.get("scheme")
    if scheme:
        qs = qs.filter(scheme=scheme)

    nsqf = params.get("nsqf")
    if nsqf == "no":
        qs = qs.filter(nsqf=None)
    elif nsqf == "yes":
        qs = qs.filter(nsqf__regex=r".+")

    qmap = {
        "Q1": ["APR", "MAY", "JUN"],
        "Q2": ["JUL", "AUG", "SEP"],
        "Q3": ["OCT", "NOV", "DEC"],
        "Q4": ["JAN", "FEB", "MAR"],
    }
    quarter = params.get("quarterly")

    if quarter:
        months = qmap.get(quarter, [])
        w = Q()
        for m in months:
            # Filter by trained_date OR certified_date (not session)
            # This ensures quarterly filters check when training/certification actually occurred
            w = (
                w
                | Q(trained_date__startswith=f"{m}-")
                | Q(certified_date__startswith=f"{m}-")
            )
        qs = qs.filter(w)

    yearly = params.get("year")
    if yearly:
        qs = qs.filter(
            Q(trained_date__contains=yearly) | Q(certified_date__contains=yearly)
        )

    return qs


def student_to_dict(s, selected_quarter=None):
    # Calculate claimable amount based on selected quarter if provided
    if selected_quarter:
        claimable = float(s.get_claimable_amount_for_quarter(selected_quarter))
    else:
        claimable = float(s.claimable_amount)
    
    return {
        "dob": s.dob.isoformat() if s.dob else "",
        "fee_date": s.fee_date.isoformat() if s.fee_date else "",
        "trained_date": s.trained_date or "",
        "session": s.session or "",
        "id": s.id | 0,
        "roll_number": s.roll_number,
        "batch_code": s.batch_code,
        "name": s.name,
        "father_name": s.father_name,
        "mother_name": s.mother_name,
        "gender": s.gender,
        "address": s.address,
        "qualifications": s.qualifications,
        "aadhaar": s.aadhaar,
        "course_name": s.course_name,
        "scheme": s.scheme,
        "nsqf": s.nsqf,
        "course_hour": s.course_hour,
        "course_category": s.course_category,
        "center_name": s.center_name,
        "mode": s.mode,
        "caste_category": s.caste_category,
        "fee": float(s.fee),
        "claimable_amount": claimable,
        "trained": s.trained,
        "certified": s.certified,
        "certified_date": s.certified_date,
        "placed": s.placed,
        "claimed": s.claimed,
    }


def xlrow_to_dict(s):
    return {
        "roll_number": s.roll_number,
        "batch_code": s.batch_code,
        "name": s.name,
        "father_name": s.father_name,
        "mother_name": s.mother_name,
        "dob": s.dob.strftime("%Y-%m-%d") if s.dob else "",
        "gender": s.gender,
        "address": s.address,
        "qualifications": s.qualifications,
        "aadhaar": s.aadhaar,
        "course_name": s.course_name,
        "scheme": s.scheme,
        "nsqf": s.nsqf,
        "course_hour": s.course_hour,
        "center_name": s.center_name,
        "mode": s.mode,
        "caste_category": s.caste_category,
        "fee": float(s.fee),
        "fee_date": s.fee_date or "",
        "trained_date": s.trained_date,
        "certified_date": s.certified_date,
        "placed": s.placed,
        "claimed": s.claimed,
        "session": s.session,
    }


def center_summary(qs):
    summary = {
        "Total": qs.count(),
        "SC": 0,
        "ST": 0,
        "OBC": 0,
        "PWD": 0,
        "GENERAL": 0,
        "B": 0,
        "C": 0,
        "D": 0,
        "E": 0,
    }
    for s in qs:
        if s.caste_category in summary:
            summary[s.caste_category] += 1
        cat = (s.course_category or "").strip().upper()[:1]
        if cat in summary:
            summary[cat] += 1
    return summary


def login_view(request):
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST["username"],
            password=request.POST["password"],
        )
        if user:
            login(request, user)
            return redirect("dashboard")
        return render(request, "login.html", {"error": "Invalid credentials"})
    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required(login_url="/login")
@ensure_csrf_cookie
def dashboard(request):
    return render(request, "dashboard.html")


@login_required(login_url="/login")
def upload(request):
    """
    Upload Excel and create studentdata rows.
    session is taken from the upload page dropdowns (session=month, year) and stored as MON-YYYY.
    Trained/certified booleans are inferred from explicit columns or presence of trained_date/certified_date.
    If trained/certified is True but corresponding *_date is missing, set date to the selected session.

    Center-restricted users can only upload rows for their own center; rows
    with another center_name are skipped.
    """
    is_admin = request.user.is_superuser
    forced_center = None
    if not is_admin:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        forced_center = profile.center_name

    if request.method == "POST":
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES.get("file")
            month = (request.POST.get("session") or "").strip().upper()
            year = (request.POST.get("year") or "").strip()
            form_session = f"{month}-{year}" if month and year else ""

            try:
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                ws = wb.active
                success = 0
                dupes = 0
                errors = 0
                raw_headers = []
                # Build header names normalized to lower-case + underscored keys
                for cell in ws[1]:
                    value = cell.value
                    if value is None:
                        raw_headers.append("")
                    else:
                        normalized = (
                            str(value)
                            .lower()
                            .strip()
                            .replace(" ", "_")
                            .replace("-", "_")
                        )
                        raw_headers.append(normalized)

                # Map of normalized header -> model field name. Lets the same
                # upload code accept both the old lowercase template and the new
                # title-case "filtered_students" download layout.
                HEADER_ALIASES = {
                    "course_hours": "course_hour",
                    "center": "center_name",
                    "caste_category": "caste_category",
                    "course_category": "course_category",
                    "claimable_amount": "claimable_amount",
                    "session": "session",
                    "claimed": "claimed",
                }

                def normalize_row(raw_dict):
                    """Return a dict keyed by model field names."""
                    out = {}
                    for k, v in raw_dict.items():
                        if not k:
                            continue
                        if k in HEADER_ALIASES:
                            k = HEADER_ALIASES[k]
                        out[k] = v
                    return out

                for row in ws.iter_rows(min_row=2, values_only=True):
                    raw_dict = dict(zip(raw_headers, row))
                    row_dict = normalize_row(raw_dict)

                    def safe_str(val):
                        return str(val).strip() if val is not None else ""

                    aadhaar = safe_str(row_dict.get("aadhaar"))
                    if aadhaar and studentdata.objects.filter(aadhaar=aadhaar).exists():
                        dupes += 1
                        continue

                    name = safe_str(row_dict.get("name"))
                    course = safe_str(row_dict.get("course_name"))
                    if not name or not course:
                        errors += 1
                        continue

                    # Booleans: accept Yes/No, True/False, 1/0. Fall back to
                    # presence of *_date column.
                    trained_bool = parse_bool(row_dict.get("trained")) or bool(
                        safe_str(row_dict.get("trained_date"))
                    )
                    certified_bool = parse_bool(row_dict.get("certified")) or bool(
                        safe_str(row_dict.get("certified_date"))
                    )
                    placed_bool = parse_bool(row_dict.get("placed"))
                    claimed_bool = parse_bool(row_dict.get("claimed"))

                    # NSQF: in the download it is the string "True"/"False".
                    # Treat those as empty (non-NSQF) so the model choice field
                    # only ever stores real "Level N" values.
                    raw_nsqf = safe_str(row_dict.get("nsqf"))
                    if raw_nsqf.lower() in ("true", "false"):
                        raw_nsqf = ""

                    # Parse numeric fields safely
                    try:
                        course_hour_val = int(row_dict.get("course_hour") or 0)
                    except Exception:
                        course_hour_val = 0

                    try:
                        fee_val = Decimal(str(row_dict.get("fee") or 0))
                    except Exception:
                        fee_val = Decimal("0.00")

                    # Parse dates
                    dob_val = parse_date(row_dict.get("dob"))
                    fee_date_val = parse_date(row_dict.get("fee_date"))

                    # Format trained/certified dates to MON-YYYY if present
                    trained_date_val = (
                        format_session_date(safe_str(row_dict.get("trained_date")))
                        if row_dict.get("trained_date")
                        else ""
                    )
                    certified_date_val = (
                        format_session_date(safe_str(row_dict.get("certified_date")))
                        if row_dict.get("certified_date")
                        else ""
                    )

                    # If boolean True but date missing, set date to dropdown session
                    if trained_bool and not trained_date_val:
                        trained_date_val = form_session or trained_date_val
                    if certified_bool and not certified_date_val:
                        certified_date_val = form_session or certified_date_val

                    # Prefer the in-file Session column if it looks valid,
                    # otherwise fall back to the dropdown session.
                    row_session = safe_str(row_dict.get("session")).upper()
                    if not re.fullmatch(
                        r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)-\d{4}",
                        row_session,
                    ):
                        row_session = form_session

                    # Center restriction: non-admin users can only upload rows
                    # for their own center. Skip rows that point to another center.
                    row_center = safe_str(row_dict.get("center_name")) or ""
                    if forced_center and row_center and row_center != forced_center:
                        errors += 1
                        continue

                    try:
                        studentdata.objects.create(
                            session=row_session,
                            roll_number=safe_str(row_dict.get("roll_number")),
                            batch_code=safe_str(row_dict.get("batch_code")),
                            name=name,
                            father_name=safe_str(row_dict.get("father_name")),
                            mother_name=safe_str(row_dict.get("mother_name")),
                            dob=dob_val,
                            gender=safe_str(row_dict.get("gender")),
                            address=safe_str(row_dict.get("address")),
                            qualifications=safe_str(row_dict.get("qualifications")),
                            aadhaar=aadhaar,
                            course_name=course,
                            scheme=safe_str(row_dict.get("scheme")),
                            nsqf=raw_nsqf,
                            course_hour=course_hour_val,
                            mode=safe_str(row_dict.get("mode")),
                            caste_category=safe_str(row_dict.get("caste_category")),
                            center_name=forced_center or row_center,
                            fee=fee_val,
                            fee_date=fee_date_val,
                            trained=trained_bool,
                            trained_date=trained_date_val,
                            certified=certified_bool,
                            certified_date=certified_date_val,
                            placed=placed_bool,
                            claimed=claimed_bool,
                        )
                        success += 1
                    except Exception as e:
                        print(f"Error on row: {e}")
                        errors += 1

                messages.success(
                    request,
                    f"Uploaded: {success} | Duplicates skipped: {dupes} | Errors: {errors}",
                )
            except Exception as e:
                print(f"❌ Failed to open Excel: {e}")
                messages.error(request, f"Error processing file: {str(e)}")
    else:
        form = ExcelUploadForm()

    return render(request, "upload.html", {"form": form})


@login_required(login_url="/login")
def filter_students(request):
    students = apply_filters(request.GET, user=request.user)
    selected_quarter = request.GET.get("quarterly")  # Get selected quarter for claimable amount calculation
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))
    offset = (page - 1) * limit
    total = len(students) if isinstance(students, list) else students.count()

    return JsonResponse(
        {
            "results": [student_to_dict(s, selected_quarter) for s in students[offset : offset + limit]],
            "pagination": {
                "page": page,
                "limit": limit,
                "total_count": total,
                "total_pages": (total + limit - 1) // limit,
                "has_next": page < (total + limit - 1) // limit,
                "has_prev": page > 1,
            },
        }
    )


@login_required(login_url="/login")
def download_filtered_data(request):
    students = apply_filters(request.GET, user=request.user)
    selected_quarter = request.GET.get("quarterly")  # Get selected quarter for claimable amount calculation

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Filtered Students"

    headers = [
        "Roll Number",
        "Batch Code",
        "Name",
        "Father Name",
        "Mother Name",
        "DOB",
        "Gender",
        "Address",
        "Qualifications",
        "Aadhaar",
        "Course Name",
        "Scheme",
        "NSQF",
        "Course Hours",
        "Course Category",
        "Center",
        "Mode",
        "Caste Category",
        "Fee",
        "Claimable Amount",
        "Fee Date",
        "Trained",
        "Trained Date",
        "Certified",
        "Certified Date",
        "Placed",
        "Claimed",
        "Session",
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(
            start_color="CCCCCC", end_color="CCCCCC", fill_type="solid"
        )

    yn = lambda v: "Yes" if v else "No"
    for row, s in enumerate(students, 2):
        # Calculate claimable amount based on selected quarter if provided
        if selected_quarter:
            claimable = s.get_claimable_amount_for_quarter(selected_quarter)
        else:
            claimable = s.claimable_amount
        
        for col, val in enumerate(
            [
                s.roll_number,
                s.batch_code,
                s.name,
                s.father_name,
                s.mother_name,
                s.dob.strftime("%Y-%m-%d") if s.dob else "",
                s.gender,
                s.address,
                s.qualifications,
                s.aadhaar,
                s.course_name,
                s.scheme,
                s.nsqf,
                s.course_hour,
                s.course_category,
                s.center_name,
                s.mode,
                s.caste_category,
                float(s.fee),
                float(claimable),
                str(s.fee_date) if s.fee_date else "",
                yn(s.trained),
                s.trained_date,
                yn(s.certified),
                s.certified_date,
                yn(s.placed),
                yn(s.claimed),
                s.session,
            ],
            1,
        ):
            ws.cell(row=row, column=col, value=val)

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(
            max((len(str(c.value)) for c in col if c.value), default=0) + 2, 50
        )

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=filtered_students.xlsx"
    wb.save(response)
    return response


# ─── Report ──────────────────────────────────────────────────────────────────


def _session_filter_options():
    sessions = list(
        studentdata.objects.values_list("session", flat=True)
        .distinct()
        .order_by("-session")
    )
    years = sorted({s.split("-")[1] for s in sessions if "-" in s}, reverse=True)
    months = sorted({s.split("-")[0] for s in sessions if "-" in s})
    return years, months


@login_required(login_url="/login")
def download(request):
    p = request.GET
    students = studentdata.objects.all()
    # Enforce center restriction for non-superuser users
    if not request.user.is_superuser:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.center_name:
            students = students.filter(center_name=profile.center_name)
    for key in ["year", "session"]:
        if p.get(key):
            students = students.filter(session__icontains=p[key])
    if p.get("center"):
        students = students.filter(center_name=p["center"])

    grouped = {}
    for s in students:
        key = f"{s.course_category}|{s.course_name}|{s.center_name}|{s.session}"
        if key not in grouped:
            grouped[key] = {
                "category": s.course_category,
                "course_name": s.course_name,
                "course_hour": s.course_hour,
                "center_name": s.center_name,
                "session": s.session,
                "scheme": s.scheme,
                "nsqf": s.nsqf,
                **{
                    c: {"trained": 0, "certified": 0, "placed": 0, "total": 0}
                    for c in ["GENERAL", "OBC", "SC", "ST", "PWD"]
                },
            }
        caste = s.caste_category or "GENERAL"
        if caste not in grouped[key]:
            grouped[key][caste] = {"trained": 0, "certified": 0, "placed": 0, "total": 0}
        g = grouped[key][caste]
        g["total"] += 1
        if s.trained_date:
            g["trained"] += 1
        if s.certified_date:
            g["certified"] += 1
        if s.placed:
            g["placed"] += 1

    report_data = list(grouped.values())
    castes = ["GENERAL", "OBC", "SC", "ST", "PWD"]
    totals = {
        c: {"trained": 0, "certified": 0, "placed": 0, "total": 0} for c in castes
    }
    for item in report_data:
        for c in castes:
            for k in totals[c]:
                totals[c][k] += item[c][k]
    totals["grand_total"] = sum(totals[c]["total"] for c in castes)

    years, months = _session_filter_options()
    return render(
        request,
        "download.html",
        {
            "data": report_data,
            "totals": totals,
            "selected_year": p.get("year", ""),
            "selected_session": p.get("session", ""),
            "selected_center": p.get("center", ""),
            "years": years,
            "months": months,
            "centers": CENTERS,
        },
    )


@login_required(login_url="/login")
def api_download_data(request):
    p = request.GET
    students = studentdata.objects.all()
    # Enforce center restriction for non-superuser users
    if not request.user.is_superuser:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.center_name:
            students = students.filter(center_name=profile.center_name)
    for key in ["year", "session"]:
        if p.get(key):
            students = students.filter(session__icontains=p[key])
    if p.get("center"):
        students = students.filter(center_name=p["center"])

    return JsonResponse(
        {
            "results": [
                {
                    "course_category": s.course_category,
                    "course_name": s.course_name,
                    "course_hour": s.course_hour,
                    "center_name": s.center_name,
                    "scheme": s.scheme,
                    "nsqf": s.nsqf,
                    "session": s.session,
                    "caste_category": s.caste_category,
                    "trained_date": s.trained_date,
                    "certified_date": s.certified_date,
                    "placed": s.placed,
                    "fee": float(s.fee),
                    "claimable_amount": float(s.claimable_amount),
                }
                for s in students
            ]
        }
    )


# ─── Update ──────────────────────────────────────────────────────────────────


@login_required(login_url="/login")
def update_student(request, student_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        student = studentdata.objects.get(id=student_id)
    except studentdata.DoesNotExist:
        return JsonResponse({"error": "Student not found"}, status=404)

    # Block center-restricted users from editing students outside their center
    if not request.user.is_superuser:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.center_name and student.center_name != profile.center_name:
            return JsonResponse(
                {"error": "You do not have access to edit this student."}, status=403
            )

    try:
        body = json.loads(request.body)
        current_month = (
            datetime.now().strftime("%b").upper() + "-" + datetime.now().strftime("%Y")
        )

        str_fields = [
            "name",
            "father_name",
            "mother_name",
            "address",
            "qualifications",
            "aadhaar",
            "course_name",
            "scheme",
            "nsqf",
        ]
        for f in str_fields:
            if body.get(f) is not None:
                setattr(student, f, str(body[f]).strip())

        session_value = body.get("session")
        if session_value is not None:
            session_value = str(session_value).strip().upper()
            if re.fullmatch(
                r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)-\d{4}",
                session_value,
            ):
                student.session = session_value

        if body.get("batch_code"):
            student.batch_code = str(body["batch_code"]).strip().upper()

        for f in ["gender", "mode", "caste_category", "center_name"]:
            if body.get(f) is not None:
                setattr(student, f, body[f])

        for f in ["dob", "fee_date"]:
            val = body.get(f)
            if val is not None:
                setattr(student, f, val if val else None)

        try:
            student.course_hour = int(
                body.get("course_hour") or student.course_hour or 0
            )
        except (ValueError, TypeError):
            student.course_hour = 0

        try:
            student.fee = float(body.get("fee") or student.fee or 0)
        except (ValueError, TypeError):
            student.fee = 0.0

        if body.get("placed") is not None:
            student.placed = body["placed"]

        # Inside update_student view:
        current_session_label = datetime.now().strftime("%b-%Y").upper()

        for field in ["trained", "certified"]:
            new_val = body.get(field)
            if new_val is not None:
                date_field = f"{field}_date"
                date_val = body.get(date_field)
                if new_val:
                    if date_val:
                        setattr(student, date_field, format_session_date(date_val))
                    elif not getattr(student, date_field):
                        setattr(student, date_field, current_session_label)
                else:
                    setattr(student, date_field, "")
                setattr(student, field, new_val)

        if body.get("claimed") is not None:
            student.claimed = body["claimed"]

        student.save()
        return JsonResponse(
            {
                "success": True,
                "course_category": student.course_category,
                "claimable_amount": float(student.claimable_amount),
                "trained_date": student.trained_date,
                "certified_date": student.certified_date,
                "claimed": student.claimed,
            }
        )

    except json.JSONDecodeError as e:
        return JsonResponse(
            {"success": False, "error": f"Invalid JSON: {e}"}, status=400
        )
    except Exception as e:
        print(traceback.format_exc())
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required(login_url="/login")
def inputView(request):
    is_admin = request.user.is_superuser
    forced_center = None
    if not is_admin:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        forced_center = profile.center_name

    if request.method == "POST":
        form = StudentDataForm(request.POST, user=request.user)
        if form.is_valid():
            student = form.save(commit=False)
            # Force center for non-admin users (don't trust POST data)
            if forced_center:
                student.center_name = forced_center
            if student.trained and not student.trained_date:
                student.trained_date = student.session
            if student.certified and not student.certified_date:
                student.certified_date = student.session
            student.save()
            return redirect("dashboard")
    else:
        form = StudentDataForm(user=request.user)

    return render(
        request,
        "input.html",
        {
            "form": form,
            "months": [
                "JAN",
                "FEB",
                "MAR",
                "APR",
                "MAY",
                "JUN",
                "JUL",
                "AUG",
                "SEP",
                "OCT",
                "NOV",
                "DEC",
            ],
            "years": list(range(2020, 2031)),
        },
    )


# ─── Overview ────────────────────────────────────────────────────────────────


def _overview_context(request_or_params, user=None, selected_session=""):
    """
    Build the overview page context with support for many filters:
      session, year, quarter, center, course, mode, caste, scheme, nsqf, status
    """
    # Accept either a request or a plain dict of params
    if hasattr(request_or_params, "GET"):
        params = request_or_params.GET
    else:
        params = request_or_params

    if user is None and hasattr(request_or_params, "user"):
        user = request_or_params.user

    # Get the user's center restriction
    user_center = None
    if user and not user.is_superuser:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        user_center = profile.center_name

    students = studentdata.objects.all()

    # Hard restriction for center-restricted users
    if user_center:
        students = students.filter(center_name=user_center)

    if selected_session:
        students = students.filter(session=selected_session)

    # Year filter
    year = params.get("year") if params else None
    if year:
        students = students.filter(
            Q(trained_date__contains=year) | Q(certified_date__contains=year)
        )

    # Quarter filter
    quarter = params.get("quarter") if params else None
    if quarter:
        qmap = {
            "Q1": ["APR", "MAY", "JUN"],
            "Q2": ["JUL", "AUG", "SEP"],
            "Q3": ["OCT", "NOV", "DEC"],
            "Q4": ["JAN", "FEB", "MAR"],
        }
        months = qmap.get(quarter, [])
        w = Q()
        for m in months:
            w = w | Q(trained_date__startswith=f"{m}-") | Q(
                certified_date__startswith=f"{m}-"
            )
        students = students.filter(w)

    # Center filter (admin only - center users already restricted)
    if not user_center:
        center = params.get("center") if params else None
        if center:
            students = students.filter(center_name=center)

    # Course filter
    course = params.get("course") if params else None
    if course:
        students = students.filter(course_name=course)

    # Mode filter
    mode = params.get("mode") if params else None
    if mode:
        students = students.filter(mode=mode)

    # Caste filter
    caste = params.get("caste") if params else None
    if caste:
        students = students.filter(caste_category=caste)

    # Scheme filter
    scheme = params.get("scheme") if params else None
    if scheme:
        students = students.filter(scheme=scheme)

    # NSQF filter
    nsqf = params.get("nsqf") if params else None
    if nsqf == "yes":
        students = students.filter(nsqf__regex=r".+")
    elif nsqf == "no":
        students = students.filter(nsqf__in=[None, ""])

    # Status filters (trained/certified/placed/claimed)
    def _bool(v):
        return v in (True, "true", "True", "1", 1, "yes", "Yes")

    trained = params.get("trained") if params else None
    if trained in ("true", "True", "1", True, 1):
        students = students.filter(trained=True)
    elif trained in ("false", "False", "0", False, 0):
        students = students.filter(trained=False)

    certified = params.get("certified") if params else None
    if certified in ("true", "True", "1", True, 1):
        students = students.filter(certified=True)
    elif certified in ("false", "False", "0", False, 0):
        students = students.filter(certified=False)

    placed = params.get("placed") if params else None
    if placed in ("true", "True", "1", True, 1):
        students = students.filter(placed=True)
    elif placed in ("false", "False", "0", False, 0):
        students = students.filter(placed=False)

    claimed = params.get("claimed") if params else None
    if claimed in ("true", "True", "1", True, 1):
        students = students.filter(claimed=True)
    elif claimed in ("false", "False", "0", False, 0):
        students = students.filter(claimed=False)

    # Build the list of centers the user is allowed to see
    visible_centers = [user_center] if user_center else CENTERS

    # Status totals
    trained_count = students.filter(trained=True).count()
    certified_count = students.filter(certified=True).count()
    placed_count = students.filter(placed=True).count()
    claimed_count = students.filter(claimed=True).count()
    total_count = students.count()
    total_fee = students.aggregate(s=models.Sum("fee"))["s"] or 0
    total_claimable = (
        students.aggregate(s=models.Sum("claimable_amount"))["s"] or 0
    )
    total_claimed_amount = (
        students.filter(claimed=True)
        .aggregate(s=models.Sum("claimable_amount"))["s"]
        or 0
    )

    # Distinct values for filter dropdowns (always from the full unrestricted pool
    # so admins can still see all options)
    full_qs = studentdata.objects.all()
    if user_center:
        full_qs = full_qs.filter(center_name=user_center)
    sessions = list(
        full_qs.values_list("session", flat=True).distinct().order_by("-session")
    )
    courses = list(
        full_qs.values_list("course_name", flat=True).distinct().order_by("course_name")
    )
    schemes = list(
        full_qs.exclude(scheme__isnull=True)
        .exclude(scheme__exact="")
        .values_list("scheme", flat=True)
        .distinct()
        .order_by("scheme")
    )
    years_set = set()
    for d in full_qs.values_list("trained_date", "certified_date"):
        for v in d:
            if v and "-" in v:
                parts = v.split("-")
                if len(parts) == 2 and parts[1].isdigit():
                    years_set.add(parts[1])
    years = sorted(years_set, reverse=True)

    return {
        "all_record": total_count,
        "trained_count": trained_count,
        "certified_count": certified_count,
        "placed_count": placed_count,
        "claimed_count": claimed_count,
        "total_fee": float(total_fee),
        "total_claimable": float(total_claimable),
        "total_claimed_amount": float(total_claimed_amount),
        "centers": [
            {
                "name": n.capitalize(),
                "stats": center_summary(students.filter(center_name=n)),
            }
            for n in visible_centers
        ],
        "sessions": sessions,
        "courses": courses,
        "schemes": schemes,
        "years": years,
        "selected_session": selected_session,
        "selected_filters": {
            "year": year or "",
            "quarter": quarter or "",
            "center": "" if user_center else (params.get("center") if params else "") or "",
            "course": course or "",
            "mode": mode or "",
            "caste": caste or "",
            "scheme": scheme or "",
            "nsqf": nsqf or "",
            "trained": trained or "",
            "certified": certified or "",
            "placed": placed or "",
            "claimed": claimed or "",
        },
        "user_center": user_center or "",
        "is_admin": bool(user and user.is_superuser),
    }


@login_required(login_url="/login")
def overview(request):
    ctx = _overview_context(request, request.user, request.GET.get("session", ""))
    ctx["centers"] = [(c["name"], c["stats"]) for c in ctx["centers"]]
    return render(request, "overview.html", ctx)


@login_required(login_url="/login")
def overview_data(request):
    ctx = _overview_context(request, request.user, request.GET.get("session", ""))
    return JsonResponse(ctx)


def courses(request):
    return render(
        request,
        "view_courses.html",
        {
            "It": NsqfIT.objects.all(),
            "elctro": NsqfElectronics.objects.all(),
            "dlc": Dlc.objects.all(),
        },
    )


def add_dropdown(field_name, option_list):
    col = column_index[field_name]
    col_letter = get_column_letter(col)
    # Build the formula: e.g., '"offline,online"'
    formula = '"' + ",".join(option_list) + '"'
    dv = DataValidation(type="list", formula1=formula, allow_blank=True)
    dv.error = "Please pick a value from the list."
    dv.errorTitle = "Invalid Entry"
    ws.add_data_validation(dv)
    # Apply to all rows from 2 to 1,048,576
    dv.add(col_letter + "2:" + col_letter + "1048576")


import openpyxl
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .models import studentdata


@login_required(login_url="/login")
def sample_upload(request):
    """
    Returns an Excel template that matches the layout of the
    'filtered_students' download exactly, so the file can be re-uploaded
    round-trip without any column re-mapping.

    Columns (Title Case, same as filtered_students download):
        Roll Number, Batch Code, Name, Father Name, Mother Name, DOB,
        Gender, Address, Qualifications, Aadhaar, Course Name, Scheme,
        NSQF, Course Hours, Course Category, Center, Mode, Caste Category,
        Fee, Claimable Amount, Fee Date, Trained, Trained Date, Certified,
        Certified Date, Placed, Claimed, Session
    """

    # Title-case headers matching the filtered_students download output
    headers = [
        "Roll Number",
        "Batch Code",
        "Name",
        "Father Name",
        "Mother Name",
        "DOB",
        "Gender",
        "Address",
        "Qualifications",
        "Aadhaar",
        "Course Name",
        "Scheme",
        "NSQF",
        "Course Hours",
        "Course Category",
        "Center",
        "Mode",
        "Caste Category",
        "Fee",
        "Claimable Amount",
        "Fee Date",
        "Trained",
        "Trained Date",
        "Certified",
        "Certified Date",
        "Placed",
        "Claimed",
        "Session",
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Student Data Template"

    col_num = 1
    for header in headers:
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(
            start_color="0E2238", end_color="0E2238", fill_type="solid"
        )
        col_num = col_num + 1

    ws.freeze_panes = "A2"

    column_index = {}
    idx = 1
    for h in headers:
        column_index[h] = idx
        idx = idx + 1

    def add_dropdown(field_name, options_list):
        col_num = column_index[field_name]
        col_letter = get_column_letter(col_num)

        formula = '"' + ",".join(options_list) + '"'

        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        dv.error = "Please select a value from the dropdown list."
        dv.errorTitle = "Invalid Entry"
        ws.add_data_validation(dv)

        dv.add(f"{col_letter}2:{col_letter}1048576")

    # Build dropdown options from the model's choice tuples
    centers = [c[1] for c in studentdata.CENTER_CHOICES]
    caste_choices = [c[1] for c in studentdata.CASTE_CHOICES]
    mode_choices = [c[1] for c in studentdata.MODE_CHOICES]
    gender_choices = [c[1] for c in studentdata.GENDER]
    nsqf_choices = [c[1] for c in studentdata.NSQF_LEVEL] + ["False", "True"]
    course_choices = [c[1] for c in studentdata.COURSE_CHOICES]
    qualification_choices = [c[1] for c in studentdata.HIGHEST_QUALIFICATION]

    # Schemes: pull distinct values from existing data, plus a "NON-NSQF" fallback
    scheme_options = []
    for s in studentdata.objects.values_list("scheme", flat=True).distinct():
        if s:
            scheme_options.append(s)
    if not scheme_options:
        scheme_options = ["NON-NSQF"]

    yes_no = ["Yes", "No"]

    add_dropdown("Center", centers)
    add_dropdown("Mode", mode_choices)
    add_dropdown("Caste Category", caste_choices)
    add_dropdown("Gender", gender_choices)
    add_dropdown("NSQF", nsqf_choices)
    add_dropdown("Scheme", scheme_options)
    add_dropdown("Course Name", course_choices)
    add_dropdown("Qualifications", qualification_choices)
    add_dropdown("Trained", yes_no)
    add_dropdown("Certified", yes_no)
    add_dropdown("Placed", yes_no)
    add_dropdown("Claimed", yes_no)

    # Sample row matching the filtered_students output format
    sample_row = [
        "NIELIT0001",            # Roll Number
        "FA-009",                # Batch Code
        "AASHISH KUMAR",         # Name
        "RAKESH KUMAR",          # Father Name
        "UMA",                   # Mother Name
        "2005-01-12",            # DOB
        "Male",                  # Gender
        "WEST DELHI  ,DELHI",    # Address
        "Graduation (B.Sc / B.Com / BA / BBA)",  # Qualifications
        "120230108482",          # Aadhaar
        "FSK Prime Bootcamp on AI",  # Course Name
        "Future Skill Prime",    # Scheme
        "False",                 # NSQF
        "40",                    # Course Hours
        "D - Short Term Course", # Course Category
        "inderlok",              # Center
        "offline",               # Mode
        "SC",                    # Caste Category
        "2000",                  # Fee
        "0",                     # Claimable Amount
        "",                      # Fee Date
        "Yes",                   # Trained
        "APR-2025",              # Trained Date
        "Yes",                   # Certified
        "APR-2025",              # Certified Date
        "No",                    # Placed
        "No",                    # Claimed
        "APR-2025",              # Session
    ]
    sample_col = 1
    for value in sample_row:
        ws.cell(row=2, column=sample_col, value=value)
        sample_col = sample_col + 1

    # Per-column widths for readability
    column_widths = {
        "Roll Number": 14,
        "Batch Code": 16,
        "Name": 28,
        "Father Name": 22,
        "Mother Name": 22,
        "DOB": 13,
        "Gender": 10,
        "Address": 30,
        "Qualifications": 28,
        "Aadhaar": 16,
        "Course Name": 32,
        "Scheme": 22,
        "NSQF": 10,
        "Course Hours": 10,
        "Course Category": 22,
        "Center": 14,
        "Mode": 10,
        "Caste Category": 14,
        "Fee": 10,
        "Claimable Amount": 16,
        "Fee Date": 13,
        "Trained": 10,
        "Trained Date": 14,
        "Certified": 10,
        "Certified Date": 14,
        "Placed": 10,
        "Claimed": 10,
        "Session": 12,
    }
    for col in range(1, len(headers) + 1):
        letter = get_column_letter(col)
        ws.column_dimensions[letter].width = column_widths.get(
            headers[col - 1], 16
        )

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        'attachment; filename="student_upload_template.xlsx"'
    )
    wb.save(response)
    return response
