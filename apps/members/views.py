from functools import wraps
from datetime import datetime
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.db import transaction

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from apps.members.models import Members, Department, SMSCampaign
from apps.members.forms import MemberForm, DepartmentForm
from apps.members.selectors import (
    get_all_members,
    get_member_by_id,
    get_all_departments,
    get_department_by_id,
)
from django.conf import settings
from django.utils import timezone
from apps.attendance.models import AttendanceSession, AttendanceRecord
from apps.common.mnotify import get_mnotify_balance


def admin_required(view_func):
    """
    Decorator ensuring that only authenticated users with 'admin' role or staff status
    can perform administrative operations.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in with admin credentials to continue.")
            return redirect("login")
        if getattr(request.user, 'role', None) != 'admin' and not request.user.is_staff:
            messages.error(request, "Access restricted: Only administrators have permission to perform this action.")
            return redirect("members:member_list")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def sms_authorized_required(view_func):
    """
    Ensures that only Superadmin, Clergy (Pastors), Ushers, and Staff
    can send SMS broadcasts via Mnotify.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access the SMS portal.")
            return redirect("login")

        role = getattr(request.user, 'role', '')
        can_send = (
            role in ['admin', 'pastor', 'usher', 'staff']
            or request.user.is_staff
            or request.user.is_superuser
        )
        if not can_send:
            messages.error(request, "Access restricted: Superadmin, Clergy, or Usher role required to send bulk SMS.")
            return redirect("admin_dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def usher_or_admin_required(view_func):
    """
    Allows authenticated staff (ushers, pastors, church workers, and administrators)
    to mark attendance, add members at the door, and manage registrations.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to continue.")
            return redirect("login")

        can_access = (
            getattr(request.user, 'can_mark_attendance', False)
            or getattr(request.user, 'role', None) in ['admin', 'pastor', 'usher', 'staff', 'user']
            or request.user.is_staff
            or request.user.is_superuser
        )
        if not can_access:
            messages.error(request, "Access restricted: Usher or administrative privileges required.")
            return redirect("login")

        return view_func(request, *args, **kwargs)
    return _wrapped_view



def member_list(request):
    """
    Displays cached list of church members with search and department filtering.
    """
    if not request.user.is_authenticated:
        return redirect("login")

    # Fetch from cache via selector
    all_members = get_all_members()
    departments = get_all_departments()

    search_query = request.GET.get('q', '').strip().lower()
    selected_dept = request.GET.get('department', '').strip()

    filtered_members = all_members

    if search_query:
        filtered_members = [
            m for m in filtered_members
            if (m.member_id and search_query in m.member_id.lower())
            or search_query in m.name.lower()
            or search_query in m.email.lower()
            or search_query in m.phone_number.lower()
            or (m.address and search_query in m.address.lower())
        ]

    if selected_dept:
        filtered_members = [
            m for m in filtered_members
            if str(m.department_id) == selected_dept or m.department.name.lower() == selected_dept.lower()
        ]

    is_admin = getattr(request.user, 'role', None) == 'admin' or request.user.is_staff
    can_manage_members = (
        is_admin 
        or getattr(request.user, 'role', None) in ['pastor', 'usher']
        or request.user.is_superuser
    )

    return render(request, "members/member_list.html", {
        "members": filtered_members,
        "total_count": len(all_members),
        "departments": departments,
        "search_query": search_query,
        "selected_dept": selected_dept,
        "is_admin": is_admin,
        "can_manage_members": can_manage_members,
    })


@usher_or_admin_required
def member_create(request):
    """
    Ushers & Admins: Add a new church member.
    Supports both modal submission (returning JSON or staying on page) and standard form.
    """
    if request.method == "POST":
        form = MemberForm(request.POST)
        if form.is_valid():
            member = form.save()

            from apps.attendance.utils import send_member_id_sms
            try:
                send_member_id_sms(member)
            except Exception as e:
                logger.warning(f"Could not dispatch SMS to new member: {e}")

            msg = f"Church member '{member.name}' added successfully! (ID: {member.member_id})"

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
                return JsonResponse({
                    "status": "success",
                    "message": msg,
                    "member_id": member.member_id,
                    "name": member.name,
                })

            messages.success(request, msg)
            next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or "members:member_list"
            return redirect(next_url)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
                errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
                return JsonResponse({"status": "error", "errors": errors}, status=400)

            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{field.capitalize()}: {err}")

            next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or "members:member_list"
            return redirect(next_url)
    else:
        form = MemberForm()

    return render(request, "members/member_form.html", {
        "form": form,
        "title": "Add Church Member",
        "action": "create",
    })


@usher_or_admin_required
def member_update(request, member_id):
    """
    Admin only: Edit an existing church member.
    """
    member = get_member_by_id(member_id)

    if request.method == "POST":
        form = MemberForm(request.POST, instance=member)
        if form.is_valid():
            member = form.save()
            messages.success(request, f"Member '{member.name}' updated successfully!")
            return redirect("members:member_list")
        else:
            messages.error(request, "Please correct the errors in the member form below.")
    else:
        form = MemberForm(instance=member)

    return render(request, "members/member_form.html", {
        "form": form,
        "member": member,
        "title": f"Edit Member: {member.name}",
        "action": "update",
    })


@admin_required
def member_delete(request, member_id):
    """
    Admin only: Delete a church member.
    """
    member = get_member_by_id(member_id)
    name = member.name
    member.delete()
    messages.success(request, f"Church member '{name}' has been deleted.")
    return redirect("members:member_list")



def department_list(request):
    """
    Displays list of departments along with member statistics.
    """
    if not request.user.is_authenticated:
        return redirect("login")

    departments = get_all_departments()
    all_members = get_all_members()

    # Calculate member counts per department from cached members
    dept_counts = {}
    for m in all_members:
        dept_counts[m.department_id] = dept_counts.get(m.department_id, 0) + 1

    dept_data = []
    for d in departments:
        dept_data.append({
            "department": d,
            "member_count": dept_counts.get(d.id, 0),
        })

    is_admin = getattr(request.user, 'role', None) == 'admin' or request.user.is_staff

    return render(request, "members/department_list.html", {
        "departments_data": dept_data,
        "total_departments": len(departments),
        "is_admin": is_admin,
    })


@admin_required
def department_create(request):
    """
    Admin only: Create a new church department/ministry.
    """
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save()
            messages.success(request, f"Department '{dept.name}' created successfully!")
            return redirect("members:department_list")
        else:
            messages.error(request, "Please correct the errors in the department form below.")
    else:
        form = DepartmentForm()

    return render(request, "members/department_form.html", {
        "form": form,
        "title": "Add Church Department",
        "action": "create",
    })


@admin_required
def department_update(request, department_id):
    """
    Admin only: Edit an existing department.
    """
    dept = get_department_by_id(department_id)

    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            dept = form.save()
            messages.success(request, f"Department '{dept.name}' updated successfully!")
            return redirect("members:department_list")
        else:
            messages.error(request, "Please correct the errors in the department form below.")
    else:
        form = DepartmentForm(instance=dept)

    return render(request, "members/department_form.html", {
        "form": form,
        "department": dept,
        "title": f"Edit Department: {dept.name}",
        "action": "update",
    })


@admin_required
def department_delete(request, department_id):
    """
    Admin only: Delete a department.
    """
    dept = get_department_by_id(department_id)
    name = dept.name
    # Members with on_delete=CASCADE will be deleted, or handle accordingly
    dept.delete()
    messages.success(request, f"Department '{name}' has been deleted.")
    return redirect("members:department_list")



# Shared styling constants for the Excel workbook
_HEADER_FONT = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
_HEADER_FILL = PatternFill(start_color='1052BA', end_color='1052BA', fill_type='solid')
_HEADER_ALIGNMENT = Alignment(horizontal='center', vertical='center', wrap_text=True)
_CELL_FONT = Font(name='Calibri', size=11)
_CELL_ALIGNMENT = Alignment(vertical='center', wrap_text=True)
_THIN_BORDER = Border(
    left=Side(style='thin', color='D1D5DB'),
    right=Side(style='thin', color='D1D5DB'),
    top=Side(style='thin', color='D1D5DB'),
    bottom=Side(style='thin', color='D1D5DB'),
)

TEMPLATE_COLUMNS = [
    ('A', 'Name', 30, 'Full name of the church member (e.g. Grace Mensah)'),
    ('B', 'Department', 25, 'Existing department name (e.g. Choir, Youth, Ushering)'),
    ('C', 'Email', 30, 'Unique email address (e.g. grace@example.com)'),
    ('D', 'Phone Number', 20, 'Unique phone number (e.g. +233 24 123 4567)'),
    ('E', 'Date of Birth', 18, 'Format: YYYY-MM-DD (e.g. 1995-08-20)'),
    ('F', 'Address', 40, 'Residential address or location'),
]


@usher_or_admin_required
def download_member_template(request):
    """
    Admin only: Downloads a formatted Excel template (.xlsx) for bulk member uploads.
    The template includes a header row, column instructions, a sample data row,
    and a separate 'Departments' reference sheet listing all existing departments.
    """
    wb = openpyxl.Workbook()

    # ---- Sheet 1: Members Template ----
    ws = wb.active
    ws.title = 'Members'

    # Freeze the header row
    ws.freeze_panes = 'A3'

    # Row 1: Instructions header (merged)
    ws.merge_cells('A1:F1')
    instructions_cell = ws['A1']
    instructions_cell.value = (
        'Church Attendance System — Bulk Member Upload Template. '
        'Fill in one member per row starting from row 3. '
        'Department names must match exactly (see the "Departments" sheet for valid names). '
        'Date of Birth format: YYYY-MM-DD.'
    )
    instructions_cell.font = Font(name='Calibri', italic=True, size=10, color='64748B')
    instructions_cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
    ws.row_dimensions[1].height = 40

    # Row 2: Column headers
    for col_letter, header_name, width, _ in TEMPLATE_COLUMNS:
        cell = ws[f'{col_letter}2']
        cell.value = header_name
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGNMENT
        cell.border = _THIN_BORDER
        ws.column_dimensions[col_letter].width = width

    ws.row_dimensions[2].height = 28

    # Row 3: Sample data row (light grey to show it's an example)
    sample_fill = PatternFill(start_color='F1F5F9', end_color='F1F5F9', fill_type='solid')
    sample_font = Font(name='Calibri', size=11, italic=True, color='94A3B8')

    departments = get_all_departments()
    first_dept_name = departments[0].name if departments else 'Choir'

    sample_data = [
        'Grace Mensah',
        first_dept_name,
        'grace.mensah@example.com',
        '+233 24 123 4567',
        '1995-08-20',
        '14 Calvary Road, Accra',
    ]

    for idx, (col_letter, _, _, _) in enumerate(TEMPLATE_COLUMNS):
        cell = ws[f'{col_letter}3']
        cell.value = sample_data[idx]
        cell.font = sample_font
        cell.fill = sample_fill
        cell.alignment = _CELL_ALIGNMENT
        cell.border = _THIN_BORDER

    ws.row_dimensions[3].height = 22

    # Rows 4+: Empty rows with borders for user data entry (pre-format 50 rows)
    for row_num in range(4, 54):
        for col_letter, _, _, _ in TEMPLATE_COLUMNS:
            cell = ws[f'{col_letter}{row_num}']
            cell.font = _CELL_FONT
            cell.alignment = _CELL_ALIGNMENT
            cell.border = _THIN_BORDER

    # ---- Sheet 2: Departments Reference ----
    ws_dept = wb.create_sheet(title='Departments')
    ws_dept.freeze_panes = 'A2'

    # Header
    dept_headers = [('A', 'Department Name', 30), ('B', 'Description', 50)]
    for col_letter, header_name, width in dept_headers:
        cell = ws_dept[f'{col_letter}1']
        cell.value = header_name
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGNMENT
        cell.border = _THIN_BORDER
        ws_dept.column_dimensions[col_letter].width = width

    ws_dept.row_dimensions[1].height = 28

    # Department rows
    for row_idx, dept in enumerate(departments, start=2):
        name_cell = ws_dept[f'A{row_idx}']
        name_cell.value = dept.name
        name_cell.font = Font(name='Calibri', size=11, bold=True)
        name_cell.alignment = _CELL_ALIGNMENT
        name_cell.border = _THIN_BORDER

        desc_cell = ws_dept[f'B{row_idx}']
        desc_cell.value = dept.description or ''
        desc_cell.font = _CELL_FONT
        desc_cell.alignment = _CELL_ALIGNMENT
        desc_cell.border = _THIN_BORDER

    if not departments:
        ws_dept['A2'].value = 'No departments created yet. Add departments first before bulk uploading members.'
        ws_dept['A2'].font = Font(name='Calibri', italic=True, color='EF4444')
        ws_dept.merge_cells('A2:B2')

    # ---- Serve the file ----
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f'church_members_template_{datetime.now().strftime("%Y%m%d")}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@usher_or_admin_required
def bulk_upload_members(request):
    """
    Admin only: Handles bulk member upload from an Excel (.xlsx) file.
    Validates each row, creates members within a transaction, and reports
    successes, skips, and errors back to the user.
    """
    if request.method != 'POST':
        return render(request, 'members/bulk_upload.html', {
            'departments': get_all_departments(),
        })

    uploaded_file = request.FILES.get('excel_file')

    if not uploaded_file:
        messages.error(request, "Please select an Excel file to upload.")
        return redirect('members:bulk_upload')

    # Validate file extension
    if not uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
        messages.error(request, "Invalid file format. Please upload a .xlsx Excel file.")
        return redirect('members:bulk_upload')

    # Validate file size (max 5MB)
    if uploaded_file.size > 5 * 1024 * 1024:
        messages.error(request, "File is too large. Maximum upload size is 5 MB.")
        return redirect('members:bulk_upload')

    try:
        wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
    except Exception:
        messages.error(request, "Could not read the uploaded file. Please ensure it is a valid .xlsx Excel file.")
        return redirect('members:bulk_upload')

    ws = wb.active

    # Build a case-insensitive department lookup from the database
    departments = {d.name.strip().lower(): d for d in Department.objects.all()}

    # Track results
    created_count = 0
    skipped_count = 0
    errors = []

    # Pre-load existing emails and phones for fast duplicate checking
    existing_emails = set(
        Members.objects.values_list('email', flat=True)
    )
    existing_phones = set(
        Members.objects.values_list('phone_number', flat=True)
    )

    rows_to_create = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        # Skip completely empty rows
        if not row or all(cell is None or str(cell).strip() == '' for cell in row):
            continue

        # Pad short rows with None
        row_data = list(row) + [None] * (6 - len(row)) if len(row) < 6 else list(row)

        raw_name = row_data[0]
        raw_dept = row_data[1]
        raw_email = row_data[2]
        raw_phone = row_data[3]
        raw_dob = row_data[4]
        raw_address = row_data[5]

        # --- Field validation ---
        row_errors = []

        # Name (required)
        name = str(raw_name).strip() if raw_name else ''
        if not name:
            row_errors.append('Name is required')

        # Department (required, must exist)
        dept_name = str(raw_dept).strip() if raw_dept else ''
        dept_obj = departments.get(dept_name.lower()) if dept_name else None
        if not dept_name:
            row_errors.append('Department is required')
        elif dept_obj is None:
            row_errors.append(f'Department "{dept_name}" does not exist')

        # Email (required, must be unique)
        email = str(raw_email).strip().lower() if raw_email else ''
        if not email:
            row_errors.append('Email is required')
        elif email in existing_emails:
            row_errors.append(f'Email "{email}" already exists')
            skipped_count += 1

        # Phone (required, must be unique)
        phone = str(raw_phone).strip() if raw_phone else ''
        if not phone:
            row_errors.append('Phone number is required')
        elif phone in existing_phones:
            row_errors.append(f'Phone "{phone}" already exists')

        # Date of Birth (required)
        dob = None
        if raw_dob:
            if isinstance(raw_dob, datetime):
                dob = raw_dob.date()
            elif isinstance(raw_dob, str):
                raw_dob_str = raw_dob.strip()
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'):
                    try:
                        dob = datetime.strptime(raw_dob_str, fmt).date()
                        break
                    except ValueError:
                        continue
                if dob is None:
                    row_errors.append(f'Invalid date format "{raw_dob_str}". Use YYYY-MM-DD')
            else:
                try:
                    dob = raw_dob
                except Exception:
                    row_errors.append('Invalid date of birth value')
        else:
            row_errors.append('Date of birth is required')

        # Address (required)
        address = str(raw_address).strip() if raw_address else ''
        if not address:
            row_errors.append('Address is required')

        if row_errors:
            errors.append({
                'row': row_idx,
                'name': name or '(empty)',
                'issues': row_errors,
            })
            continue

        # Add to batch
        existing_emails.add(email)
        existing_phones.add(phone)
        rows_to_create.append(Members(
            department=dept_obj,
            name=name,
            email=email,
            phone_number=phone,
            date_of_birth=dob,
            address=address,
        ))

    wb.close()

    # Bulk create inside a transaction
    if rows_to_create:
        try:
            with transaction.atomic():
                # Use bulk_create; iterate individual saves so signals fire for cache invalidation
                for member in rows_to_create:
                    member.save()
                created_count = len(rows_to_create)
        except Exception as e:
            messages.error(request, f"Database error during bulk insert: {str(e)}")
            return redirect('members:bulk_upload')

    # Build result summary
    if created_count > 0:
        messages.success(
            request,
            f"Successfully imported {created_count} church member{'s' if created_count != 1 else ''}!"
        )

    if errors:
        error_summary = f"{len(errors)} row{'s' if len(errors) != 1 else ''} had errors and were skipped."
        messages.warning(request, error_summary)

    if created_count == 0 and not errors:
        messages.info(request, "The uploaded file contained no data rows to import.")

    return render(request, 'members/bulk_upload_results.html', {
        'created_count': created_count,
        'error_count': len(errors),
        'errors': errors,
        'total_processed': created_count + len(errors),
    })



@sms_authorized_required
def sms_recipient_count(request):
    """
    AJAX helper to quickly count recipients for a selected target type.
    """
    target_type = request.GET.get('target_type', 'all')
    dept_id = request.GET.get('department_id')
    session_id = request.GET.get('session_id')

    count = 0

    if target_type == 'all':
        count = Members.objects.exclude(phone_number='').exclude(phone_number__isnull=True).count()
    elif target_type == 'department' and dept_id:
        count = Members.objects.filter(department_id=dept_id).exclude(phone_number='').exclude(phone_number__isnull=True).count()
    elif target_type == 'session_present' and session_id:
        count = AttendanceRecord.objects.filter(session_id=session_id).exclude(member__phone_number='').exclude(member__phone_number__isnull=True).count()
    elif target_type == 'session_absent' and session_id:
        present_ids = AttendanceRecord.objects.filter(session_id=session_id).values_list('member_id', flat=True)
        count = Members.objects.exclude(id__in=present_ids).exclude(phone_number='').exclude(phone_number__isnull=True).count()
    elif target_type == 'birthday':
        today = timezone.localdate()
        count = Members.objects.filter(
            date_of_birth__month=today.month,
            date_of_birth__day=today.day
        ).exclude(phone_number='').exclude(phone_number__isnull=True).count()
    elif target_type == 'custom':
        custom_input = request.GET.get('custom_numbers', '')
        nums = [n.strip() for n in re.split(r'[,;\s\n]+', custom_input) if n.strip()]
        count = len(nums)

    return JsonResponse({'status': 'success', 'count': count})


@sms_authorized_required
def bulk_sms_view(request):
    """
    Mnotify Bulk SMS Management:
    Allows superadmin, clergy (pastors), and ushers to broadcast SMS to:
    - All church members
    - Specific department(s)
    - Attendees present at a specific service session
    - Absent church members from a service session (follow-up)
    - Custom phone numbers
    """
    if request.method == "POST":
        target_type = request.POST.get('target_type', 'all').strip()
        dept_id = request.POST.get('department_id', '').strip()
        session_id = request.POST.get('session_id', '').strip()
        custom_numbers_text = request.POST.get('custom_numbers', '').strip()
        sender_id = request.POST.get('sender_id', '').strip() or getattr(settings, 'MNOTIFY_SENDER_ID', 'CHURCH')
        sender_id = sender_id[:11]  # Mnotify maximum 11 alphanumeric characters
        message = request.POST.get('message', '').strip()
        title = request.POST.get('title', '').strip()

        if not message:
            messages.error(request, "SMS Message text cannot be empty.")
            return redirect('members:bulk_sms')

        phone_numbers = []
        dept_obj = None
        session_obj = None
        target_display = "All Congregants"

        # 1. Resolve Target Phone Numbers
        if target_type == 'all':
            target_display = "All Congregants"
            phone_numbers = list(
                Members.objects.exclude(phone_number='').exclude(phone_number__isnull=True).values_list('phone_number', flat=True)
            )
        elif target_type == 'department':
            if not dept_id:
                messages.error(request, "Please select a church department for this SMS broadcast.")
                return redirect('members:bulk_sms')
            dept_obj = get_object_or_404(Department, id=dept_id)
            target_display = f"Department: {dept_obj.name}"
            phone_numbers = list(
                Members.objects.filter(department=dept_obj).exclude(phone_number='').exclude(phone_number__isnull=True).values_list('phone_number', flat=True)
            )
        elif target_type == 'session_present':
            if not session_id:
                messages.error(request, "Please select an attendance service session.")
                return redirect('members:bulk_sms')
            session_obj = get_object_or_404(AttendanceSession, id=session_id)
            target_display = f"Present at {session_obj.title}"
            phone_numbers = list(
                AttendanceRecord.objects.filter(session=session_obj).select_related('member').exclude(member__phone_number='').exclude(member__phone_number__isnull=True).values_list('member__phone_number', flat=True)
            )
        elif target_type == 'session_absent':
            if not session_id:
                messages.error(request, "Please select an attendance service session.")
                return redirect('members:bulk_sms')
            session_obj = get_object_or_404(AttendanceSession, id=session_id)
            target_display = f"Absent from {session_obj.title}"
            present_member_ids = AttendanceRecord.objects.filter(session=session_obj).values_list('member_id', flat=True)
            phone_numbers = list(
                Members.objects.exclude(id__in=present_member_ids).exclude(phone_number='').exclude(phone_number__isnull=True).values_list('phone_number', flat=True)
            )
        elif target_type == 'birthday':
            today = timezone.localdate()
            target_display = f"Birthday Celebrants ({today.strftime('%b %d')})"
            birthday_members = Members.objects.filter(
                date_of_birth__month=today.month,
                date_of_birth__day=today.day
            ).exclude(phone_number='').exclude(phone_number__isnull=True)
            phone_numbers = list(birthday_members.values_list('phone_number', flat=True))

            if not phone_numbers:
                messages.warning(request, f"No members have birthdays today ({today.strftime('%B %d')}). No messages were queued.")
                return redirect('members:bulk_sms')

            # Create campaign & dispatch personalized task
            campaign = SMSCampaign.objects.create(
                sender_user=request.user,
                title=title or f"Birthday Wishes - {today.strftime('%b %d, %Y')}",
                target_type='birthday',
                sender_id=sender_id,
                message=message,
                recipient_count=len(phone_numbers),
                status='pending',
            )

            from apps.common.tasks import send_birthday_wishes_task
            send_birthday_wishes_task.delay(
                custom_message=message,
                sender_id=sender_id,
                target_date_str=str(today),
                campaign_id=str(campaign.id),
            )

            messages.success(
                request,
                f"Birthday wishes queued for {len(phone_numbers)} celebrant(s) today! Personalized SMS is being delivered in the background."
            )

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
                return JsonResponse({
                    'status': 'success',
                    'message': f"Birthday wishes queued for {len(phone_numbers)} celebrants.",
                    'total_sent': len(phone_numbers),
                    'campaign_id': str(campaign.id),
                })

            return redirect('members:bulk_sms')
        elif target_type == 'custom':
            target_display = "Custom Phone Numbers"
            raw_nums = re.split(r'[,;\s\n]+', custom_numbers_text)
            phone_numbers = [n.strip() for n in raw_nums if n.strip()]

        if not phone_numbers:
            messages.warning(request, f"No valid phone numbers found for target: '{target_display}'. No messages were sent.")
            return redirect('members:bulk_sms')

        # 2. Create SMSCampaign record with 'pending' status
        campaign = SMSCampaign.objects.create(
            sender_user=request.user,
            title=title or f"{target_display} ({len(phone_numbers)} recipients)",
            target_type=target_type,
            department=dept_obj,
            session_title=session_obj.title if session_obj else '',
            sender_id=sender_id,
            message=message,
            recipient_count=len(phone_numbers),
            status='pending',
        )

        # 3. Dispatch via Celery background task (async)
        from apps.common.tasks import send_bulk_sms_task
        send_bulk_sms_task.delay(
            phone_numbers=phone_numbers,
            message=message,
            sender_id=sender_id,
            campaign_id=str(campaign.id),
        )

        messages.success(
            request,
            f"SMS broadcast queued for {len(phone_numbers)} recipient(s) targeting '{target_display}'. "
            f"Delivery is being processed in the background."
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
            return JsonResponse({
                'status': 'success',
                'message': f"SMS broadcast queued for {len(phone_numbers)} recipient(s).",
                'total_sent': len(phone_numbers),
                'campaign_id': str(campaign.id),
            })

        return redirect('members:bulk_sms')

    # GET Request: Prepare SMS Broadcast Dashboard

    today = timezone.localdate()
    today_birthdays = Members.objects.filter(
        date_of_birth__month=today.month,
        date_of_birth__day=today.day
    ).exclude(phone_number='').exclude(phone_number__isnull=True)
    today_birthdays_count = today_birthdays.count()

    departments = Department.objects.all().order_by('name')
    recent_sessions = AttendanceSession.objects.order_by('-date', '-start_time')[:10]
    total_members_count = Members.objects.exclude(phone_number='').exclude(phone_number__isnull=True).count()
    campaigns = SMSCampaign.objects.select_related('sender_user', 'department')[:15]
    balance_info = get_mnotify_balance()

    default_sender = getattr(settings, 'MNOTIFY_SENDER_ID', 'CHURCH')

    return render(request, "members/bulk_sms.html", {
        "departments": departments,
        "recent_sessions": recent_sessions,
        "total_members_count": total_members_count,
        "campaigns": campaigns,
        "balance_info": balance_info,
        "default_sender": default_sender,
        "today_birthdays": today_birthdays,
        "today_birthdays_count": today_birthdays_count,
    })



