/* Antojitos y Más — CRM · Main JS */

// ── Clock ──────────────────────────────────────────────────────────────────
function updateClock() {
    const el = document.getElementById('headerClock');
    if (!el) return;
    const now = new Date();
    const options = { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' };
    el.textContent = now.toLocaleDateString('es-CO', options);
}
updateClock();
setInterval(updateClock, 30000);

// ── Sidebar Toggle ─────────────────────────────────────────────────────────
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
    document.body.style.overflow = sidebar.classList.contains('open') ? 'hidden' : '';
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (!sidebar) return;
    sidebar.classList.remove('open');
    overlay.classList.remove('open');
    document.body.style.overflow = '';
}

// Close sidebar on Escape key
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeSidebar();
});

// ── Auto-dismiss Alerts ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.alert.custom-alert').forEach(alert => {
        setTimeout(() => {
            try {
                bootstrap.Alert.getOrCreateInstance(alert).close();
            } catch (_) {}
        }, 4500);
    });
});

// ── Format currency ───────────────────────────────────────────────────────
function formatCOP(amount) {
    return '$' + parseInt(amount).toLocaleString('es-CO');
}

// ── Utility: prevent double-submit on forms ───────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', () => {
            const btn = form.querySelector('[type="submit"]');
            if (btn && !btn.dataset.noDisable) {
                setTimeout(() => { btn.disabled = true; }, 50);
            }
        });
    });
});
