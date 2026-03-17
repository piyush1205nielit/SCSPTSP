from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
import openpyxl

from .forms import ExcelUploadForm
from .models import studentdata


# ─── Auth ────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required(login_url='/login')
def dashboard(request):
    return render(request, 'dashboard.html')


# ─── Upload ──────────────────────────────────────────────────────────────────

def parse_bool_field(value):
    """Excel cells can have True/False, 'yes'/'no', 1/0 — normalize all to bool."""
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in ['true', 'yes', '1']:
        return True
    return False


def parse_date_field(value):
    """
    Expects a string like 'JAN-2024' or 'January-2024' or 'Jan 2024'.
    Returns normalized 'JAN-2024' or empty string if nothing useful.
    """
    if not value:
        return ''
    val = str(value).strip().upper().replace(' ', '-')
    return val  # store as-is, e.g. "JAN-2024"


@login_required(login_url='/login')
def upload(request):
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['file']
            year = form.cleaned_data['year']
            session = form.cleaned_data['session']
            session_label = f"{session.upper()[:3]}-{year}"  # e.g. "JAN-2024"

            try:
                wb = openpyxl.load_workbook(excel_file)
                sheet = wb.active

                headers = [
                    str(cell.value).lower().strip() if cell.value else ''
                    for cell in sheet[1]
                ]

                success_count = 0
                error_count = 0

                for row in sheet.iter_rows(min_row=2, values_only=True):
                    if all(cell is None for cell in row):
                        continue

                    try:
                        row_data = {headers[i]: row[i] for i in range(len(headers)) if i < len(row)}

                        name = str(row_data.get('name') or '').strip()
                        roll_number = str(row_data.get('roll_number') or '').strip()
                        course_name = str(row_data.get('course_name') or '').strip()
                        scheme = str(row_data.get('scheme') or '').strip()

                        # course_hour
                        try:
                            course_hour = int(float(str(row_data.get('course_hour') or 0)))
                        except (ValueError, TypeError):
                            course_hour = 0

                        # fee
                        try:
                            fee = float(str(row_data.get('fee') or 0))
                        except (ValueError, TypeError):
                            fee = 0

                        # mode
                        mode = str(row_data.get('mode') or 'offline').lower().strip()
                        if mode not in ['offline', 'online']:
                            mode = 'offline'

                        # caste
                        caste = str(row_data.get('caste_category') or 'GENERAL').upper().strip()
                        if caste not in ['OBC', 'SC', 'ST', 'PWD', 'GENERAL']:
                            caste = 'GENERAL'

                        # center
                        center = str(row_data.get('center_name') or 'inderlok').lower().strip()
                        if center not in ['inderlok', 'janakpuri', 'karkardooma']:
                            center = 'inderlok'

                        trained_date = parse_date_field(row_data.get('trained_date'))
                        certified_date = parse_date_field(row_data.get('certified_date'))
                        placed = parse_bool_field(row_data.get('placed', False))
                        nsqf = str(row_data.get('nsqf') or '').strip()
                        if not name or not course_name or course_hour <= 0:
                            error_count += 1
                            continue

                        student = studentdata(
                            session=session_label,
                            roll_number=roll_number,
                            name=name,
                            course_name=course_name,
                            course_hour=course_hour,
                            scheme=scheme,
                            nsqf=nsqf,
                            mode=mode,
                            caste_category=caste,
                            center_name=center,
                            fee=fee,
                            trained_date=trained_date,
                            certified_date=certified_date,
                            placed=placed
                        )
                        student.save()  # course_category and claimable_amount auto-set in model.save()
                        success_count += 1

                    except Exception as e:
                        error_count += 1
                        print(f"Row error: {e}")

                messages.success(request, f'Uploaded {success_count} records. Skipped: {error_count}')

            except Exception as e:
                messages.error(request, f'Error reading file: {str(e)}')

            return redirect('upload')

    else:
        form = ExcelUploadForm()

    return render(request, 'upload.html', {'form': form})


# ─── Filter (AJAX) ───────────────────────────────────────────────────────────

@login_required(login_url='/login')
def filter_students(request):
    students = studentdata.objects.all()

    center    = request.GET.get('center')
    mode      = request.GET.get('mode')
    caste     = request.GET.get('caste')
    trained   = request.GET.get('trained')    # 'true' / 'false' / ''
    certified = request.GET.get('certified')
    placed    = request.GET.get('placed')
    session   = request.GET.get('session')
    scheme = request.GET.get('scheme')
    nsqf   = request.GET.get('nsqf')   # 'yes' / 'no'

    if center:
        students = students.filter(center_name=center)
    if mode:
        students = students.filter(mode=mode)
    if caste:
        students = students.filter(caste_category=caste)
    if session:
        students = students.filter(session__icontains=session)
    if trained:
        students = students.filter(trained_date__gt='') if trained == 'true' else students.exclude(trained_date__gt='')
    if certified:
        students = students.filter(certified_date__gt='') if certified == 'true' else students.exclude(certified_date__gt='')
    if placed:
        students = students.filter(placed=(placed.lower() == 'true'))
    

    if scheme:
        students = students.filter(scheme__icontains=scheme)
    if nsqf:
        if nsqf == 'yes':
            students = students.exclude(nsqf='').exclude(nsqf__isnull=True)
        elif nsqf == 'no':
            students = students.filter(nsqf='') | students.filter(nsqf__isnull=True)

    data = [
    {
        'name': s.name,
        'roll_number': s.roll_number,
        'course_name': s.course_name,
        'scheme': s.scheme,        # ← this was missing
        'nsqf': s.nsqf,
        'course_hour': s.course_hour,
        'course_category': s.course_category,
        'center_name': s.center_name,
        'mode': s.mode,
        'caste_category': s.caste_category,
        'fee': float(s.fee),
        'claimable_amount': float(s.claimable_amount),
        'trained_date': s.trained_date,
        'certified_date': s.certified_date,
        'placed': s.placed,
        'session': s.session,
    }
    for s in students
]
    return JsonResponse({'results': data})


# ─── Download Report ─────────────────────────────────────────────────────────

@login_required(login_url='/login')
def download(request):
    year    = request.GET.get('year', '')
    session = request.GET.get('session', '')
    center  = request.GET.get('center', '')

    students = studentdata.objects.all()
    if year:
        students = students.filter(session__icontains=year)
    if session:
        students = students.filter(session__icontains=session)
    if center:
        students = students.filter(center_name=center)

    # Group by: category | course_name | center_name | session
    grouped = {}
    for s in students:
        key = f"{s.course_category}|{s.course_name}|{s.center_name}|{s.session}"
        if key not in grouped:
            grouped[key] = {
                'category':    s.course_category,
                'course_name': s.course_name,
                'course_hour': s.course_hour,
                'center_name': s.center_name,
                'session':     s.session,
            }
            for c in ['GENERAL', 'OBC', 'SC', 'ST', 'PWD']:
                grouped[key][c] = {'trained': 0, 'certified': 0, 'placed': 0, 'total': 0}

        caste = s.caste_category
        grouped[key][caste]['total'] += 1
        if s.trained_date:
            grouped[key][caste]['trained'] += 1
        if s.certified_date:
            grouped[key][caste]['certified'] += 1
        if s.placed:
            grouped[key][caste]['placed'] += 1

    report_data = list(grouped.values())

    # Grand totals
    totals = {c: {'trained': 0, 'certified': 0, 'placed': 0, 'total': 0} for c in ['GENERAL', 'OBC', 'SC', 'ST', 'PWD']}
    totals['grand_total'] = 0
    for item in report_data:
        for c in ['GENERAL', 'OBC', 'SC', 'ST', 'PWD']:
            for key in ['trained', 'certified', 'placed', 'total']:
                totals[c][key] += item[c][key]
            totals['grand_total'] += item[c]['total']
    # grand_total was being double-counted above, fix:
    totals['grand_total'] = sum(totals[c]['total'] for c in ['GENERAL', 'OBC', 'SC', 'ST', 'PWD'])

    context = {
        'data': report_data,
        'totals': totals,
        'selected_year': year,
        'selected_session': session,
        'selected_center': center,
        'years': [str(y) for y in range(2020, 2026)],
        'sessions': ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                     'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'],
    }
    return render(request, 'download.html', context)


# ─── API endpoint for JS-driven Excel export ─────────────────────────────────

@login_required(login_url='/login')
def api_download_data(request):
    year    = request.GET.get('year', '')
    session = request.GET.get('session', '')
    center  = request.GET.get('center', '')

    students = studentdata.objects.all()
    if year:
        students = students.filter(session__icontains=year)
    if session:
        students = students.filter(session__icontains=session)
    if center:
        students = students.filter(center_name=center)

    data = [
        {
            'course_category':  s.course_category,
            'course_name':      s.course_name,
            'course_hour':      s.course_hour,
            'center_name':      s.center_name,
            'nsqf': s.nsqf,
            'session':          s.session,
            'caste_category':   s.caste_category,
            'trained_date':     s.trained_date,
            'certified_date':   s.certified_date,
            'placed':           s.placed,
            'fee':              float(s.fee),
            'claimable_amount': float(s.claimable_amount),
        }
        for s in students
    ]

    return JsonResponse({'results': data})