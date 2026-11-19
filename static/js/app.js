/**
 * Church Attendance System - Main Interactive JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    initPasswordToggles();
    initPasswordStrengthMeters();
    initTableSearchAndFilter();
    initDeleteModal();
    initAvatarPreview();
    initToastAutoDismiss();
});

/**
 * 1. Toggle Password Visibility (Eye Icon)
 */
function initPasswordToggles() {
    const toggleButtons = document.querySelectorAll('[data-target]');
    toggleButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (!input) return;

            const eyeOpen = btn.querySelector('.eye-open');
            const eyeClosed = btn.querySelector('.eye-closed');

            if (input.type === 'password') {
                input.type = 'text';
                if (eyeOpen) eyeOpen.classList.add('hidden');
                if (eyeClosed) eyeClosed.classList.remove('hidden');
            } else {
                input.type = 'password';
                if (eyeOpen) eyeOpen.classList.remove('hidden');
                if (eyeClosed) eyeClosed.classList.add('hidden');
            }
        });
    });
}

/**
 * 2. Real-Time Password Strength Meter
 */
function initPasswordStrengthMeters() {
    const pwdInputs = document.querySelectorAll('#id_new_password1, #id_password');
    const bar = document.getElementById('password-strength-bar');
    const text = document.getElementById('password-strength-text');

    if (!bar || !text) return;

    pwdInputs.forEach(input => {
        input.addEventListener('input', () => {
            const val = input.value;
            let score = 0;

            if (val.length >= 8) score += 1;
            if (val.length >= 12) score += 1;
            if (/[A-Z]/.test(val)) score += 1;
            if (/[0-9]/.test(val)) score += 1;
            if (/[^A-Za-z0-9]/.test(val)) score += 1;

            if (val.length === 0) {
                bar.style.width = '0%';
                bar.className = 'h-full transition-all duration-300 bg-slate-300';
                text.textContent = 'Too Short';
                text.className = 'text-slate-500';
            } else if (score <= 1) {
                bar.style.width = '25%';
                bar.className = 'h-full transition-all duration-300 bg-red-500';
                text.textContent = 'Weak';
                text.className = 'text-red-600 font-bold';
            } else if (score <= 3) {
                bar.style.width = '60%';
                bar.className = 'h-full transition-all duration-300 bg-amber-500';
                text.textContent = 'Medium';
                text.className = 'text-amber-600 font-bold';
            } else if (score === 4) {
                bar.style.width = '85%';
                bar.className = 'h-full transition-all duration-300 bg-blue-600';
                text.textContent = 'Strong';
                text.className = 'text-blue-600 font-bold';
            } else {
                bar.style.width = '100%';
                bar.className = 'h-full transition-all duration-300 bg-emerald-500';
                text.textContent = 'Very Strong';
                text.className = 'text-emerald-600 font-bold';
            }
        });
    });
}

/**
 * 3. Member Directory Instant Live Search & Role Filtering
 */
function initTableSearchAndFilter() {
    const searchInput = document.getElementById('user-search-input');
    const rows = document.querySelectorAll('.member-row');
    const visibleCountEl = document.getElementById('visible-count');
    const noResultsEl = document.getElementById('no-search-results');
    const filterBtns = document.querySelectorAll('.role-filter-btn');

    if (!rows.length) return;

    let currentRole = 'all';
    let searchQuery = '';

    function applyFilter() {
        let count = 0;
        rows.forEach(row => {
            const role = row.getAttribute('data-role') || 'user';
            const searchData = (row.getAttribute('data-search') || '').toLowerCase();

            const matchesRole = (
                currentRole === 'all' || 
                role === currentRole || 
                (currentRole === 'staff' && (role === 'staff' || role === 'user'))
            );
            const matchesSearch = !searchQuery || searchData.includes(searchQuery);

            if (matchesRole && matchesSearch) {
                row.classList.remove('hidden');
                count++;
            } else {
                row.classList.add('hidden');
            }
        });

        if (visibleCountEl) {
            visibleCountEl.textContent = count;
        }

        if (noResultsEl) {
            if (count === 0) {
                noResultsEl.classList.remove('hidden');
            } else {
                noResultsEl.classList.add('hidden');
            }
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            searchQuery = e.target.value.trim().toLowerCase();
            applyFilter();
        });
    }

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => {
                b.classList.remove('bg-white', 'shadow-xs', 'text-blue-600');
                b.classList.add('text-slate-600');
            });
            btn.classList.add('bg-white', 'shadow-xs', 'text-blue-600');
            btn.classList.remove('text-slate-600');

            currentRole = btn.getAttribute('data-role');
            applyFilter();
        });
    });
}

/**
 * 4. Delete Confirmation Modal
 */
function initDeleteModal() {
    const modal = document.getElementById('delete-modal');
    if (!modal) return;

    const memberNameEl = document.getElementById('delete-member-name');
    const confirmDeleteLink = document.getElementById('confirm-delete-link');
    const deleteButtons = document.querySelectorAll('.delete-member-btn');
    const closeButtons = modal.querySelectorAll('.close-modal-btn, .modal-backdrop');

    deleteButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const name = btn.getAttribute('data-name');
            const url = btn.getAttribute('data-url');

            if (memberNameEl) memberNameEl.textContent = name;
            if (confirmDeleteLink) confirmDeleteLink.href = url;

            modal.classList.remove('hidden');
        });
    });

    closeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            modal.classList.add('hidden');
        });
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            modal.classList.add('hidden');
        }
    });
}

/**
 * 5. Avatar File Upload Preview
 */
function initAvatarPreview() {
    const avatarInput = document.getElementById('id_avatar');
    const previewContainer = document.getElementById('avatar-preview-container');

    if (!avatarInput || !previewContainer) return;

    avatarInput.addEventListener('change', () => {
        const file = avatarInput.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                previewContainer.innerHTML = `<img src="${e.target.result}" alt="Preview" class="w-full h-full object-cover">`;
            };
            reader.readAsDataURL(file);
        }
    });
}

/**
 * 6. Flash Messages Toast Auto-Dismiss
 */
function initToastAutoDismiss() {
    const toasts = document.querySelectorAll('.message-toast');
    toasts.forEach(toast => {
        setTimeout(() => {
            toast.classList.add('opacity-0', 'translate-y-2');
            setTimeout(() => toast.remove(), 400);
        }, 4500);
    });
}

/**
 * 7. Guest Access Notification / Demo
 */
function continueAsGuest() {
    showToast('Guest Mode: You are continuing in public visitor mode with limited viewing privileges.', 'info');
    // If you wish to redirect guests or log them into a guest session:
    // window.location.href = '/dashboard/';
}

/**
 * 8. Global Modals & Unified Sidebar Controllers
 */
function openAddMemberModal() {
    const modal = document.getElementById('global-add-member-modal');
    if (modal) {
        modal.classList.remove('hidden');
        const firstInput = modal.querySelector('input[name="name"]');
        if (firstInput) setTimeout(() => firstInput.focus(), 100);
    }
}

function closeAddMemberModal() {
    const modal = document.getElementById('global-add-member-modal');
    if (modal) modal.classList.add('hidden');
}

function openQuickAttendanceModal() {
    const modal = document.getElementById('global-quick-attendance-modal');
    if (modal) {
        modal.classList.remove('hidden');
        const alertBox = document.getElementById('quick-checkin-alert');
        if (alertBox) alertBox.classList.add('hidden');
        const input = document.getElementById('quick-member-id-input');
        if (input) {
            input.value = '';
            setTimeout(() => input.focus(), 100);
        }
    }
}

function closeQuickAttendanceModal() {
    const modal = document.getElementById('global-quick-attendance-modal');
    if (modal) modal.classList.add('hidden');
}

function toggleMenu(menuId) {
    const menu = document.getElementById(menuId);
    const arrow = document.getElementById(menuId.replace('-menu', '-arrow'));
    if (menu) menu.classList.toggle('hidden');
    if (arrow) arrow.classList.toggle('rotate-180');
}

function toggleDropdown(id) {
    const d = document.getElementById(id);
    if (d) d.classList.toggle('hidden');
}

// ── Mobile Sidebar Drawer ──────────────────────────────────────────
// Uses CSS classes defined in input.css for reliability with Tailwind v4
// (Tailwind only generates CSS for classes it sees in templates;
//  JS-only class additions like translate-x-0 would be unstyled.)

function openSidebar() {
    const sidebar  = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar) return;

    sidebar.classList.add('sidebar-open');
    if (backdrop) backdrop.classList.add('backdrop-open');
    document.body.classList.add('sidebar-is-open');
}

function closeSidebar() {
    const sidebar  = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    if (!sidebar) return;

    sidebar.classList.remove('sidebar-open');
    if (backdrop) backdrop.classList.remove('backdrop-open');
    document.body.classList.remove('sidebar-is-open');
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    sidebar.classList.contains('sidebar-open') ? closeSidebar() : openSidebar();
}

/** Called from each sidebar link — closes drawer only on mobile */
function closeSidebarOnMobile() {
    if (window.innerWidth < 1024) closeSidebar();
}

// Wire up backdrop + close button after DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const backdrop = document.getElementById('sidebar-backdrop');
    const closeBtn = document.getElementById('sidebar-close');

    if (backdrop) backdrop.addEventListener('click', closeSidebar);
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);

    // ESC closes sidebar on mobile
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const sidebar = document.getElementById('sidebar');
            if (sidebar && sidebar.classList.contains('sidebar-open')) {
                closeSidebar();
            }
        }
    });
});

// Close modals on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAddMemberModal();
        closeQuickAttendanceModal();
    }
});

// Setup AJAX for Quick Attendance Modal Form
document.addEventListener('DOMContentLoaded', () => {
    const checkinForm = document.getElementById('global-quick-attendance-form');
    if (checkinForm) {
        checkinForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('quick-checkin-submit-btn');
            const alertBox = document.getElementById('quick-checkin-alert');
            const input = document.getElementById('quick-member-id-input');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="inline-block animate-spin mr-2">⟳</span> Checking In...';

            const formData = new FormData(checkinForm);
            formData.append('is_ajax', '1');

            try {
                const response = await fetch(checkinForm.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    body: formData
                });
                const data = await response.json();

                alertBox.classList.remove('hidden', 'bg-red-50', 'text-red-900', 'border-red-200', 'bg-emerald-50', 'text-emerald-900', 'border-emerald-200', 'bg-blue-50', 'text-blue-900', 'border-blue-200');

                if (response.ok) {
                    if (data.status === 'already_checked_in') {
                        alertBox.classList.add('bg-blue-50', 'text-blue-900', 'border-blue-200');
                        alertBox.innerHTML = `<strong>Notice:</strong> ${data.message}`;
                        showToast(data.message, 'info');
                    } else {
                        alertBox.classList.add('bg-emerald-50', 'text-emerald-900', 'border-emerald-200');
                        alertBox.innerHTML = `<strong>Success!</strong> ${data.message}`;
                        showToast(data.message, 'success');
                    }
                    input.value = '';
                    input.focus();
                } else {
                    alertBox.classList.add('bg-red-50', 'text-red-900', 'border-red-200');
                    alertBox.innerHTML = `<strong>Error:</strong> ${data.message || 'Check-in failed.'}`;
                    showToast(data.message || 'Check-in failed', 'error');
                }
            } catch (err) {
                alertBox.classList.remove('hidden');
                alertBox.classList.add('bg-red-50', 'text-red-900', 'border-red-200');
                alertBox.textContent = 'Network or server error. Please try again.';
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        });
    }

    const memberForm = document.getElementById('global-add-member-form');
    if (memberForm) {
        memberForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submit-member-btn');
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="inline-block animate-spin mr-2">⟳</span> Saving...';

            const formData = new FormData(memberForm);
            formData.append('is_ajax', '1');

            try {
                const response = await fetch(memberForm.action, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    body: formData
                });
                const data = await response.json();

                if (response.ok) {
                    showToast(`✓ Member ${data.name} added! (ID: ${data.member_id})`, 'success');
                    memberForm.reset();
                    closeAddMemberModal();
                    if (window.location.pathname.includes('/members')) {
                        setTimeout(() => window.location.reload(), 600);
                    }
                } else {
                    let errMsg = 'Please check the form: ';
                    if (data.errors) {
                        for (const k in data.errors) {
                            errMsg += `${k}: ${data.errors[k].join(', ')} `;
                        }
                    }
                    showToast(errMsg, 'error');
                }
            } catch (err) {
                showToast('Failed to save member. Please verify data.', 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        });
    }
});
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const bgClass = type === 'error' ? 'bg-red-50 text-red-900 border-red-200' :
                    type === 'success' ? 'bg-emerald-50 text-emerald-900 border-emerald-200' :
                    'bg-blue-50 text-blue-900 border-blue-200';

    toast.className = `pointer-events-auto flex items-start gap-3 p-4 rounded-xl shadow-lg border text-sm transition-all duration-300 transform translate-y-0 opacity-100 ${bgClass}`;
    toast.innerHTML = `
        <div class="flex-1 font-medium leading-relaxed">${message}</div>
        <button type="button" onclick="this.closest('div').remove()" class="text-slate-400 hover:text-slate-700 transition">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
        </button>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 400);
    }, 4500);
}
