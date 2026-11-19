import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime, date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.urls import reverse

from apps.members.models import Members, Location, Department
from apps.members.views import admin_required, usher_or_admin_required
from .models import AttendanceSession, AttendanceRecord
from .forms import AttendanceSessionForm, LocationForm, CheckInForm, QuickMemberCheckInForm
from .utils import verify_geofence, haversine_distance, send_member_id_sms, generate_qr_code_base64



def _process_check_in(request, session, church_loc, is_entrance=False):
    """
    Shared core processor for geofenced check-in.
    Used by both the permanent entrance QR and session-specific QR codes.
    """
    success_record = None
    already_checked_in = False
    error_message = None
    geofence_error = None

    if request.method == "POST":
        form = CheckInForm(request.POST)
        if form.is_valid():
            member_id_input = form.cleaned_data['member_id'].strip().upper()
            user_lat = form.cleaned_data['latitude']
            user_lon = form.cleaned_data['longitude']
            device_info = form.cleaned_data.get('device_info', '')

            # 1. GEOFENCING SECURITY CHECK
            is_inside, distance, geo_msg = verify_geofence(user_lat, user_lon, church_loc)

            if not is_inside:
                geofence_error = {
                    "distance": distance,
                    "radius": church_loc.radius,
                    "message": (
                        f"Check-In Blocked: You are outside the church premises (~{distance:.1f} meters away). "
                        f"The allowed church radius is {church_loc.radius:.0f} meters. "
                        f"Even if this link was shared with you, attendance cannot be recorded outside church grounds."
                    )
                }
            else:
                # 2. MEMBER ID VALIDATION
                member = Members.objects.filter(member_id__iexact=member_id_input).select_related('department').first()

                if not member:
                    error_message = (
                        f"Member ID '{member_id_input}' was not found in our records. "
                        f"Please check your SMS or contact the church usher for assistance."
                    )
                else:
                    # 3. DUPLICATE CHECK-IN PREVENTION
                    existing_record = AttendanceRecord.objects.filter(
                        session=session,
                        member=member
                    ).first()

                    if existing_record:
                        already_checked_in = True
                        success_record = existing_record
                    else:
                        # 4. MARK ATTENDANCE
                        success_record = AttendanceRecord.objects.create(
                            session=session,
                            member=member,
                            latitude=user_lat,
                            longitude=user_lon,
                            distance_meters=distance,
                            status='present',
                            device_info=device_info or "Mobile QR Check-In"
                        )
        else:
            if 'latitude' in form.errors or 'longitude' in form.errors:
                error_message = "Your GPS location is required to verify you are on church premises. Please enable location permissions."
            else:
                error_message = "Please enter a valid Member ID."
    else:
        form = CheckInForm()

    return render(request, "attendance/check_in.html", {
        "session": session,
        "church_location": church_loc,
        "form": form,
        "success_record": success_record,
        "already_checked_in": already_checked_in,
        "error_message": error_message,
        "geofence_error": geofence_error,
        "is_entrance": is_entrance,
        "hide_sidebar": True,
    })


def entrance_check_in(request, location_id=None):
    """
    Permanent Entrance Check-In endpoint accessed when scanning the entrance QR code.
    Dynamically identifies the location and looks up the currently active service session.
    If a session is active, processes the GPS geofenced check-in for that session.
    If no session is currently active, informs the congregant that check-in is closed.
    """
    if location_id:
        church_loc = get_object_or_404(Location, id=location_id)
    else:
        church_loc = Location.objects.first()

    if not church_loc:
        return render(request, "attendance/entrance_closed.html", {
            "church_location": None,
            "reason": "Church sanctuary location has not been configured yet. Please contact the administrator.",
            "hide_sidebar": True,
        })

    # Find the current active service session for this location
    active_session = AttendanceSession.objects.filter(
        location=church_loc,
        is_active=True
    ).order_by('-date', '-start_time').first()

    if not active_session:
        return render(request, "attendance/entrance_closed.html", {
            "church_location": church_loc,
            "reason": (
                f"Welcome to {church_loc.name}! There is no active church service session open right now. "
                f"Check-in is automatically activated during our scheduled church services (e.g. Sunday Morning, Midweek Service). "
                f"If you are attending a service right now and see this, please speak with an usher at the entrance desk."
            ),
            "hide_sidebar": True,
        })

    return _process_check_in(request, active_session, church_loc, is_entrance=True)


def check_in(request, session_code):
    """
    Session-specific check-in endpoint accessed when scanning a specific session's QR code.
    Enforces device GPS Geolocation and Geofencing against church premises.
    """
    session = get_object_or_404(
        AttendanceSession.objects.select_related('location'),
        session_code=session_code
    )

    # Verify session is currently active
    if not session.is_active:
        return render(request, "attendance/check_in_closed.html", {
            "session": session,
            "reason": "This attendance session has ended or is currently closed by the church administrator.",
            "hide_sidebar": True,
        })

    return _process_check_in(request, session, session.location, is_entrance=False)


# -------------------------------------------------------------
# ADMIN SESSION MANAGEMENT & QR DISPLAY
# -------------------------------------------------------------

@admin_required
def session_list(request):
    """
    Admin overview of all attendance sessions.
    """
    sessions = AttendanceSession.objects.select_related('location').prefetch_related('records').all()
    locations = Location.objects.all()

    return render(request, "attendance/session_list.html", {
        "sessions": sessions,
        "locations": locations,
        "total_sessions": sessions.count(),
        "active_sessions": sessions.filter(is_active=True).count(),
    })


@admin_required
def session_create(request):
    """
    Admin creates a new attendance session.
    """
    if request.method == "POST":
        form = AttendanceSessionForm(request.POST)
        if form.is_valid():
            session = form.save()
            messages.success(request, f"Attendance session '{session.title}' created successfully!")
            return redirect("attendance:session_detail", session_id=session.id)
        else:
            messages.error(request, "Please correct the errors in the form below.")
    else:
        # Default to first location if available
        initial_loc = Location.objects.first()
        form = AttendanceSessionForm(initial={'location': initial_loc})

    return render(request, "attendance/session_form.html", {
        "form": form,
        "title": "Create Attendance Session",
        "action": "create",
        "locations_count": Location.objects.count(),
    })


@admin_required
def session_detail(request, session_id):
    """
    Live Screen for Church Projectors / Entrance Posters:
    Displays high-resolution QR Code, Live Attendee Counter, and Recent Check-ins.
    Supports real-time JSON polling for live auto-updating.
    """
    session = get_object_or_404(
        AttendanceSession.objects.select_related('location'),
        id=session_id
    )

    records = session.records.select_related('member', 'member__department').order_by('-check_in_time')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        recent_records_data = [
            {
                'id': str(r.id),
                'name': r.member.name,
                'member_id': r.member.member_id,
                'department': r.member.department.name if r.member.department else '',
                'initial': r.member.name[:1].upper() if r.member.name else '?',
                'time': r.check_in_time.strftime('%I:%M %p'),
                'distance': f"{r.distance_meters:.1f}m" if r.distance_meters is not None else "0m",
            }
            for r in records[:15]
        ]
        return JsonResponse({
            'status': 'success',
            'is_active': session.is_active,
            'total_records': records.count(),
            'records': recent_records_data,
        })

    qr_code_base64 = session.get_qr_code_base64(request=request)
    checkin_url = session.get_checkin_url(request=request)

    return render(request, "attendance/session_detail.html", {
        "session": session,
        "records": records[:15],
        "total_records": records.count(),
        "qr_code_base64": qr_code_base64,
        "checkin_url": checkin_url,
    })


@admin_required
def session_records(request, session_id):
    """
    Detailed table of all attendees for a service with search & filtering.
    """
    session = get_object_or_404(
        AttendanceSession.objects.select_related('location'),
        id=session_id
    )

    query = request.GET.get('q', '').strip().lower()
    records_qs = session.records.select_related('member', 'member__department').order_by('-check_in_time')

    if query:
        records_qs = [
            r for r in records_qs
            if query in r.member.name.lower()
            or query in r.member.member_id.lower()
            or query in r.member.phone_number.lower()
            or query in r.member.department.name.lower()
        ]

    return render(request, "attendance/session_records.html", {
        "session": session,
        "records": records_qs,
        "query": query,
        "total_attendees": session.records.count(),
    })


@admin_required
def session_toggle_active(request, session_id):
    """
    Quick toggle to open or close check-in for a service.
    """
    session = get_object_or_404(AttendanceSession, id=session_id)
    session.is_active = not session.is_active
    session.save()
    status_str = "opened" if session.is_active else "closed"
    messages.success(request, f"Attendance check-in for '{session.title}' is now {status_str}.")
    return redirect("attendance:session_list")


@admin_required
def session_delete(request, session_id):
    """
    Admin deletes a church service session and its associated attendance records.
    If the session no longer exists (stale link), redirect gracefully instead of 404.
    """
    try:
        session = AttendanceSession.objects.get(id=session_id)
    except AttendanceSession.DoesNotExist:
        messages.warning(
            request,
            "That service session no longer exists — it may have already been deleted."
        )
        return redirect("attendance:session_list")

    title = session.title
    date_str = session.date.strftime('%b %d, %Y')

    if request.method == "POST":
        session.delete()
        messages.success(request, f"Service '{title}' ({date_str}) and all its attendance records have been permanently deleted.")
        return redirect("attendance:session_list")

    # GET → show confirmation page
    return render(request, "attendance/session_confirm_delete.html", {
        "session": session,
    })


@admin_required
def session_export_excel(request, session_id):
    """
    Exports attendee list to Excel spreadsheet using openpyxl.
    """
    session = get_object_or_404(
        AttendanceSession.objects.select_related('location'),
        id=session_id
    )
    records = session.records.select_related('member', 'member__department').order_by('check_in_time')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance List"

    # Styling
    header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1052BA", end_color="1052BA", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")

    # Title Banner
    ws.merge_cells("A1:G1")
    title_cell = ws["A1"]
    title_cell.value = f"Attendance Register: {session.title} — {session.date.strftime('%B %d, %Y')}"
    title_cell.font = Font(name="Calibri", bold=True, size=13, color="1052BA")
    title_cell.alignment = left_align
    ws.row_dimensions[1].height = 30

    headers = [
        ("A", "#", 6),
        ("B", "Member ID", 15),
        ("C", "Full Name", 28),
        ("D", "Department", 22),
        ("E", "Phone Number", 20),
        ("F", "Check-In Time", 18),
        ("G", "Distance from Church", 22),
    ]

    for col, name, width in headers:
        cell = ws[f"{col}2"]
        cell.value = name
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        ws.column_dimensions[col].width = width
    ws.row_dimensions[2].height = 25

    for idx, r in enumerate(records, start=1):
        row_num = idx + 2
        ws[f"A{row_num}"] = idx
        ws[f"A{row_num}"].alignment = center_align
        ws[f"B{row_num}"] = r.member.member_id
        ws[f"B{row_num}"].alignment = center_align
        ws[f"C{row_num}"] = r.member.name
        ws[f"D{row_num}"] = r.member.department.name
        ws[f"E{row_num}"] = r.member.phone_number
        ws[f"F{row_num}"] = r.check_in_time.strftime("%I:%M %p")
        ws[f"F{row_num}"].alignment = center_align
        ws[f"G{row_num}"] = f"{r.distance_meters} m"
        ws[f"G{row_num}"].alignment = center_align

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    safe_title = session.title.replace(' ', '_')
    filename = f"Attendance_{safe_title}_{session.date.strftime('%Y%m%d')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


# -------------------------------------------------------------
# SMS MEMBER ID DISPATCH & LOCATION MANAGEMENT
# -------------------------------------------------------------

@usher_or_admin_required
def send_member_sms(request, member_id):
    """
    Ushers & Admins trigger sending the Member ID to the member via Mnotify SMS
    (especially useful when a congregant has forgotten their Member ID for check-in).
    """
    member = get_object_or_404(Members, id=member_id)

    if not member.phone_number:
        msg = f"Cannot send SMS: '{member.name}' does not have a phone number on record."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': msg}, status=400)
        messages.error(request, msg)
        return redirect(request.META.get('HTTP_REFERER', 'members:member_list'))

    success = send_member_id_sms(member)
    if success:
        msg = f"Member ID ({member.member_id}) was sent via SMS to {member.name} ({member.phone_number})."
        messages.success(request, msg)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': msg, 'member_id': member.member_id})
    else:
        msg = f"Failed to dispatch SMS to {member.phone_number}. Please check Mnotify settings/balance."
        messages.warning(request, msg)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'warning', 'message': msg}, status=502)

    return redirect(request.META.get('HTTP_REFERER', 'members:member_list'))


@admin_required
def location_list(request):
    """
    Admin management of church premises and geofence locations.
    """
    locations = Location.objects.all()
    return render(request, "attendance/location_list.html", {
        "locations": locations,
    })


@admin_required
def location_create(request):
    """
    Admin sets up a new church premise GPS location & geofence radius.
    """
    if request.method == "POST":
        form = LocationForm(request.POST)
        if form.is_valid():
            loc = form.save()
            messages.success(request, f"Church location '{loc.name}' configured with {loc.radius}m radius.")
            return redirect("attendance:location_list")
    else:
        form = LocationForm(initial={'radius': 100})

    return render(request, "attendance/location_form.html", {
        "form": form,
        "title": "Configure Church Sanctuary Location & Geofence",
        "action": "create",
    })


@admin_required
def location_update(request, location_id):
    """
    Admin edits an existing church location / radius.
    """
    loc = get_object_or_404(Location, id=location_id)
    if request.method == "POST":
        form = LocationForm(request.POST, instance=loc)
        if form.is_valid():
            loc = form.save()
            messages.success(request, f"Church location '{loc.name}' updated successfully.")
            return redirect("attendance:location_list")
    else:
        form = LocationForm(instance=loc)

    return render(request, "attendance/location_form.html", {
        "form": form,
        "location": loc,
        "title": f"Edit Geofence: {loc.name}",
        "action": "update",
    })


def location_calibrate(request, location_id):
    """
    One-click GPS calibration endpoint.
    Updates the church location GPS coordinates and sets a healthy radius (default 150m)
    directly from a physical device currently present at the sanctuary.
    """
    loc = get_object_or_404(Location, id=location_id)
    if request.method == "POST":
        try:
            lat = float(request.POST.get('latitude'))
            lon = float(request.POST.get('longitude'))
            radius = float(request.POST.get('radius', loc.radius or 150))
            if radius < 20:
                radius = 150.0  # Safe recommended default for churches

            loc.latitude = lat
            loc.longitude = lon
            loc.radius = radius
            loc.save()

            return JsonResponse({
                'status': 'success',
                'message': f"Successfully calibrated '{loc.name}' coordinates to ({lat:.6f}, {lon:.6f}) with {radius:.0f}m radius.",
                'latitude': lat,
                'longitude': lon,
                'radius': radius
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)



# -------------------------------------------------------------
# USHER / VOLUNTEER MANUAL CHECK-IN & FAST REGISTRATION DESK
# -------------------------------------------------------------

@usher_or_admin_required
def usher_desk(request, session_id=None):
    """
    Dedicated Usher Desk interface:
    Allows ushers/volunteers to manually check in congregants who do not have
    a smartphone, had battery failure, or need assistance, and quickly register
    new congregants who are not yet in the portal.
    """
    # 1. Determine active session
    if session_id:
        session = get_object_or_404(
            AttendanceSession.objects.select_related('location'),
            id=session_id
        )
    else:
        # Get active session today or most recent active session
        session = (
            AttendanceSession.objects.filter(is_active=True, date=timezone.now().date())
            .select_related('location')
            .first()
        )
        if not session:
            session = (
                AttendanceSession.objects.filter(is_active=True)
                .select_related('location')
                .first()
            )

    all_sessions = AttendanceSession.objects.filter(is_active=True).order_by('-date')

    # If no active session exists at all, inform usher to create or activate one
    if not session:
        return render(request, "attendance/usher_no_session.html", {
            "all_sessions": AttendanceSession.objects.all()[:10]
        })

    # 2. Get attendees already checked into this session
    checked_in_member_ids = set(
        AttendanceRecord.objects.filter(session=session).values_list('member_id', flat=True)
    )

    # 3. Search and filter congregants
    query = request.GET.get('q', '').strip()
    members_qs = Members.objects.select_related('department').all().order_by('name')

    if query:
        members_qs = members_qs.filter(
            models.Q(name__icontains=query) |
            models.Q(member_id__icontains=query) |
            models.Q(phone_number__icontains=query) |
            models.Q(department__name__icontains=query)
        )

    # Attach checked-in boolean to each member
    members_data = []
    for m in members_qs:
        is_present = m.id in checked_in_member_ids
        members_data.append({
            "member": m,
            "is_present": is_present,
        })

    quick_form = QuickMemberCheckInForm()
    total_present = len(checked_in_member_ids)
    total_congregants = Members.objects.count()

    return render(request, "attendance/usher_desk.html", {
        "session": session,
        "all_sessions": all_sessions,
        "members_data": members_data,
        "total_present": total_present,
        "total_congregants": total_congregants,
        "query": query,
        "quick_form": quick_form,
    })


@usher_or_admin_required
def usher_mark_checkin(request, session_id, member_id):
    """
    Action: Usher manually marks a congregant as PRESENT for a session.
    """
    session = get_object_or_404(AttendanceSession.objects.select_related('location'), id=session_id)
    member = get_object_or_404(Members, id=member_id)

    # Check if already recorded
    record, created = AttendanceRecord.objects.get_or_create(
        session=session,
        member=member,
        defaults={
            'latitude': session.location.latitude,
            'longitude': session.location.longitude,
            'distance_meters': 0.0,
            'status': 'present',
            'device_info': f"Usher Desk ({request.user.first_name or request.user.email})"
        }
    )

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            "status": "success",
            "created": created,
            "member_id": member.member_id,
            "member_name": member.name,
            "check_in_time": record.check_in_time.strftime("%I:%M %p"),
            "message": f"Checked in {member.name} ({member.member_id}) successfully!"
        })

    if created:
        messages.success(request, f"Checked in {member.name} ({member.member_id}) as PRESENT.")
    else:
        messages.info(request, f"{member.name} was already checked in.")

    return redirect(request.META.get('HTTP_REFERER', 'attendance:usher_desk'))


@usher_or_admin_required
def usher_undo_checkin(request, session_id, member_id):
    """
    Action: Usher undoes a check-in made by mistake.
    """
    session = get_object_or_404(AttendanceSession, id=session_id)
    member = get_object_or_404(Members, id=member_id)

    deleted_count, _ = AttendanceRecord.objects.filter(session=session, member=member).delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            "status": "success",
            "message": f"Undid check-in for {member.name}"
        })

    if deleted_count:
        messages.warning(request, f"Check-in removed for {member.name}.")

    return redirect(request.META.get('HTTP_REFERER', 'attendance:usher_desk'))


@usher_or_admin_required
def usher_quick_add_member(request, session_id):
    """
    Action: Usher registers a first-time visitor or new congregant at the door
    who is not yet in the portal and marks them PRESENT immediately.
    """
    session = get_object_or_404(AttendanceSession.objects.select_related('location'), id=session_id)

    if request.method == "POST":
        form = QuickMemberCheckInForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name'].strip()
            phone = form.cleaned_data['phone_number'].strip()
            dept = form.cleaned_data['department']
            raw_email = form.cleaned_data.get('email', '').strip().lower()
            dob = form.cleaned_data.get('date_of_birth') or date(2000, 1, 1)
            address = form.cleaned_data.get('address', '').strip() or 'Sanctuary Congregation'

            # If member didn't provide an email, generate a safe placeholder
            if not raw_email:
                phone_clean = ''.join(ch for ch in phone if ch.isdigit())
                raw_email = f"member_{phone_clean}@church.local"

            # Check if phone number already exists
            existing_member = Members.objects.filter(phone_number=phone).first()
            if existing_member:
                # Mark existing member present
                record, created = AttendanceRecord.objects.get_or_create(
                    session=session,
                    member=existing_member,
                    defaults={
                        'latitude': session.location.latitude,
                        'longitude': session.location.longitude,
                        'distance_meters': 0.0,
                        'status': 'present',
                        'device_info': f"Usher Desk Quick ({request.user.first_name})"
                    }
                )
                messages.info(request, f"Member with phone {phone} was already registered as {existing_member.name} ({existing_member.member_id}) and has been checked in!")
                return redirect("attendance:usher_desk_session", session_id=session.id)

            # Create new member (automatically generates FY-XXXX Member ID)
            new_member = Members.objects.create(
                name=name,
                phone_number=phone,
                department=dept,
                email=raw_email,
                date_of_birth=dob,
                address=address,
            )

            # Send Member ID via SMS so they have it on their phone
            try:
                send_member_id_sms(new_member)
            except Exception:
                pass

            # Immediately check them in for today's service
            AttendanceRecord.objects.create(
                session=session,
                member=new_member,
                latitude=session.location.latitude,
                longitude=session.location.longitude,
                distance_meters=0.0,
                status='present',
                device_info=f"Usher Desk Registered ({request.user.first_name or request.user.email})"
            )

            messages.success(
                request,
                f"New congregant '{new_member.name}' was registered (ID: {new_member.member_id}) and checked in as PRESENT! SMS sent."
            )
            return redirect("attendance:usher_desk_session", session_id=session.id)
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, f"{field.capitalize()}: {err}")
    
    return redirect("attendance:usher_desk_session", session_id=session.id)


# -------------------------------------------------------------
# PERMANENT ENTRANCE POSTER & ATTENDANCE DASHBOARD
# -------------------------------------------------------------

@usher_or_admin_required
def entrance_poster(request, location_id=None):
    """
    Generates a high-resolution, printable A4 / Entrance Standee poster
    featuring the church logo, permanent entrance QR code, and 3-step check-in guide.
    """
    if location_id:
        location = get_object_or_404(Location, id=location_id)
    else:
        location = Location.objects.first()

    all_locations = Location.objects.all()

    if location:
        checkin_url = request.build_absolute_uri(
            reverse('attendance:entrance_checkin_loc', kwargs={'location_id': location.id})
        )
    else:
        checkin_url = request.build_absolute_uri(reverse('attendance:entrance_checkin'))

    qr_code_base64 = generate_qr_code_base64(checkin_url)

    return render(request, "attendance/entrance_poster.html", {
        "location": location,
        "all_locations": all_locations,
        "checkin_url": checkin_url,
        "qr_code_base64": qr_code_base64,
        "hide_sidebar": True,
    })


def _get_filtered_attendance_qs(request):
    """
    Helper function to build the filtered AttendanceRecord queryset
    shared between the dashboard view and the Excel export.
    """
    qs = AttendanceRecord.objects.select_related(
        'session', 'member', 'member__department', 'session__location'
    ).all()

    date_filter = request.GET.get('date', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    month_filter = request.GET.get('month', '').strip()
    year_filter = request.GET.get('year', '').strip()
    session_filter = request.GET.get('session', '').strip()
    dept_filter = request.GET.get('department', '').strip()
    method_filter = request.GET.get('method', '').strip()
    search_query = request.GET.get('q', '').strip()

    if date_filter:
        qs = qs.filter(session__date=date_filter)
    else:
        if date_from:
            qs = qs.filter(session__date__gte=date_from)
        if date_to:
            qs = qs.filter(session__date__lte=date_to)

    if month_filter and month_filter.isdigit():
        qs = qs.filter(session__date__month=int(month_filter))

    if year_filter and year_filter.isdigit():
        qs = qs.filter(session__date__year=int(year_filter))

    if session_filter:
        qs = qs.filter(session_id=session_filter)

    if dept_filter:
        qs = qs.filter(member__department_id=dept_filter)

    if method_filter == 'usher':
        qs = qs.filter(device_info__icontains='Usher Desk')
    elif method_filter == 'qr':
        qs = qs.exclude(device_info__icontains='Usher Desk')

    if search_query:
        qs = qs.filter(
            Q(member__name__icontains=search_query) |
            Q(member__member_id__icontains=search_query) |
            Q(member__phone_number__icontains=search_query) |
            Q(session__title__icontains=search_query)
        )

    return qs.order_by('-session__date', '-check_in_time')


@usher_or_admin_required
def attendance_dashboard(request):
    """
    Central Attendance Register Dashboard with comprehensive filtering:
    - Specific Date, Date Range (from - to)
    - Month & Year dropdowns
    - Service Session
    - Department
    - Check-in Method (Self QR vs Usher Desk)
    - Member Search
    """
    qs = _get_filtered_attendance_qs(request)

    total_count = qs.count()
    usher_count = qs.filter(device_info__icontains='Usher Desk').count()
    qr_count = total_count - usher_count
    unique_members_count = qs.values('member').distinct().count()
    unique_depts_count = qs.values('member__department').distinct().count()

    sessions_list = AttendanceSession.objects.order_by('-date', '-start_time')[:35]
    departments_list = Department.objects.order_by('name')

    current_year = timezone.now().year
    years_list = list(range(current_year, current_year - 5, -1))
    months_list = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    return render(request, "attendance/attendance_dashboard.html", {
        "records": qs[:500],
        "total_count": total_count,
        "usher_count": usher_count,
        "qr_count": qr_count,
        "unique_members_count": unique_members_count,
        "unique_depts_count": unique_depts_count,
        "sessions_list": sessions_list,
        "departments_list": departments_list,
        "years_list": years_list,
        "months_list": months_list,
        "date_filter": request.GET.get('date', '').strip(),
        "date_from": request.GET.get('date_from', '').strip(),
        "date_to": request.GET.get('date_to', '').strip(),
        "month_filter": int(request.GET.get('month')) if request.GET.get('month', '').isdigit() else '',
        "year_filter": int(request.GET.get('year')) if request.GET.get('year', '').isdigit() else '',
        "session_filter": request.GET.get('session', '').strip(),
        "dept_filter": request.GET.get('department', '').strip(),
        "method_filter": request.GET.get('method', '').strip(),
        "search_query": request.GET.get('q', '').strip(),
    })


@usher_or_admin_required
def attendance_dashboard_export(request):
    """
    Exports the filtered attendance register directly to an Excel spreadsheet.
    """
    qs = _get_filtered_attendance_qs(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Register"

    header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1052BA", end_color="1052BA", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color="E2E8F0"),
        right=Side(style='thin', color="E2E8F0"),
        top=Side(style='thin', color="E2E8F0"),
        bottom=Side(style='thin', color="E2E8F0")
    )

    ws.merge_cells("A1:I1")
    title_cell = ws["A1"]
    title_cell.value = f"Church Attendance Register — Generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}"
    title_cell.font = Font(name="Calibri", bold=True, size=13, color="1052BA")
    title_cell.alignment = left_align
    ws.row_dimensions[1].height = 28

    headers = [
        ("A", "#", 6),
        ("B", "Date", 14),
        ("C", "Time", 12),
        ("D", "Member ID", 15),
        ("E", "Full Name", 26),
        ("F", "Department", 22),
        ("G", "Phone Number", 18),
        ("H", "Service Session", 28),
        ("I", "Check-In Method", 24),
    ]

    for col, name, width in headers:
        cell = ws[f"{col}2"]
        cell.value = name
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        ws.column_dimensions[col].width = width
    ws.row_dimensions[2].height = 24

    for idx, r in enumerate(qs, start=1):
        row_num = idx + 2
        method = "Usher Desk Manual" if "Usher Desk" in (r.device_info or '') else "Self QR Scan (GPS)"
        ws[f"A{row_num}"] = idx
        ws[f"A{row_num}"].alignment = center_align
        ws[f"B{row_num}"] = r.session.date.strftime("%Y-%m-%d")
        ws[f"B{row_num}"].alignment = center_align
        ws[f"C{row_num}"] = r.check_in_time.strftime("%I:%M %p")
        ws[f"C{row_num}"].alignment = center_align
        ws[f"D{row_num}"] = r.member.member_id
        ws[f"D{row_num}"].alignment = center_align
        ws[f"E{row_num}"] = r.member.name
        ws[f"E{row_num}"].alignment = left_align
        ws[f"F{row_num}"] = r.member.department.name if r.member.department else "—"
        ws[f"F{row_num}"].alignment = left_align
        ws[f"G{row_num}"] = r.member.phone_number
        ws[f"G{row_num}"].alignment = center_align
        ws[f"H{row_num}"] = r.session.title
        ws[f"H{row_num}"].alignment = left_align
        ws[f"I{row_num}"] = method
        ws[f"I{row_num}"].alignment = left_align

        for col, _, _ in headers:
            ws[f"{col}{row_num}"].border = thin_border

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    timestamp = timezone.now().strftime("%Y%m%d_%H%M")
    response['Content-Disposition'] = f'attachment; filename="attendance_register_{timestamp}.xlsx"'
    wb.save(response)
    return response


@usher_or_admin_required
def quick_mark_attendance(request):
    """
    Fast attendance check-in for ushers/admins from any modal.
    Can receive either member_id (e.g. FY-0001) or search by phone/name.
    """
    if request.method == "POST":
        member_id_input = request.POST.get('member_id', '').strip().upper()
        session_id = request.POST.get('session_id', '').strip()

        # Resolve session
        if session_id:
            session = get_object_or_404(AttendanceSession, id=session_id)
        else:
            session = AttendanceSession.objects.filter(is_active=True).order_by('-date', '-start_time').first()

        if not session:
            err = "No active service session is currently open. Please activate a service first."
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
                return JsonResponse({"status": "error", "message": err}, status=400)
            messages.error(request, err)
            return redirect(request.META.get('HTTP_REFERER', 'attendance:usher_desk'))

        # Look up member
        member = Members.objects.filter(
            Q(member_id__iexact=member_id_input) |
            Q(phone_number__iexact=member_id_input) |
            Q(email__iexact=member_id_input)
        ).first()

        if not member:
            err = f"Member with ID or Phone '{member_id_input}' not found. Please verify or add them first."
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
                return JsonResponse({"status": "error", "message": err}, status=404)
            messages.error(request, err)
            return redirect(request.META.get('HTTP_REFERER', 'attendance:usher_desk'))

        # Check existing attendance
        existing = AttendanceRecord.objects.filter(session=session, member=member).first()
        if existing:
            msg = f"{member.name} ({member.member_id}) was ALREADY checked in for {session.title}!"
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
                return JsonResponse({"status": "already_checked_in", "message": msg, "member_name": member.name, "member_id": member.member_id})
            messages.info(request, msg)
            return redirect(request.META.get('HTTP_REFERER', 'attendance:usher_desk'))

        # Record attendance
        rec = AttendanceRecord.objects.create(
            session=session,
            member=member,
            latitude=session.location.latitude,
            longitude=session.location.longitude,
            distance_meters=0.0,
            status='present',
            device_info=f"Usher Quick Check-in ({request.user.first_name or request.user.email})"
        )

        msg = f"✓ {member.name} ({member.member_id}) checked in as PRESENT for {session.title}!"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('is_ajax') == '1':
            return JsonResponse({"status": "success", "message": msg, "member_name": member.name, "member_id": member.member_id})

        messages.success(request, msg)
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or "attendance:usher_desk"
        return redirect(next_url)

    return redirect("attendance:usher_desk")
