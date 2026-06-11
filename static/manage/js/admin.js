/* ============================================
   SLOVOYAD ADMIN PANEL – Shared JavaScript
   ============================================ */

const API_BASE = '/manage/api';

async function apiFetch(path, options = {}) {
    const resp = await fetch(API_BASE + path, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options
    });
    if (resp.status === 401) {
        window.location.href = '/manage/login';
        return null;
    }
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
    }
    return resp.json();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('bg-BG') + ' ' + d.toLocaleTimeString('bg-BG', {hour:'2-digit',minute:'2-digit'});
}

function scoreColor(score) {
    if (score >= 8) return '#22c55e';
    if (score >= 5) return '#eab308';
    return '#ef4444';
}

function scoreClass(score) {
    if (score >= 8) return 'score-green';
    if (score >= 5) return 'score-yellow';
    return 'score-red';
}

function statusBadge(status) {
    const colors = {completed:'green', running:'yellow', pending:'blue', failed:'red', processing:'yellow'};
    const labels = {completed:'Завършен', running:'В процес', pending:'Чакащ', failed:'Грешка', processing:'Обработва се'};
    return `<span class="admin-badge admin-badge-${colors[status] || 'blue'}">${labels[status] || status}</span>`;
}

function showToast(message, type = 'error') {
    const existing = document.querySelector('.admin-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `admin-toast admin-toast-${type}`;
    toast.innerHTML = `
        <span>${escapeHtml(message)}</span>
        <button onclick="this.parentElement.remove()">&times;</button>
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function confirmModal(title, message) {
    return new Promise(resolve => {
        const modal = document.createElement('div');
        modal.className = 'admin-modal';
        modal.innerHTML = `
            <div class="admin-modal-content admin-card">
                <h3 style="margin-bottom: 0.75rem; color: var(--text-primary);">${escapeHtml(title)}</h3>
                <p style="color: var(--text-secondary); margin-bottom: 1.5rem; font-size: 0.9rem;">${escapeHtml(message)}</p>
                <div class="admin-modal-actions">
                    <button class="admin-btn admin-btn-ghost" id="modal-cancel">Отказ</button>
                    <button class="admin-btn admin-btn-danger" id="modal-confirm">Изтрий</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        modal.querySelector('#modal-cancel').onclick = () => { modal.remove(); resolve(false); };
        modal.querySelector('#modal-confirm').onclick = () => { modal.remove(); resolve(true); };
        modal.addEventListener('click', (e) => { if (e.target === modal) { modal.remove(); resolve(false); } });
    });
}

// Sidebar active link
function setupSidebar() {
    const path = window.location.pathname;
    document.querySelectorAll('.admin-nav a').forEach(link => {
        const href = link.getAttribute('href');
        if (path === href || (href !== '/manage' && href !== '/manage/' && path.startsWith(href))) {
            link.classList.add('active');
        } else if ((href === '/manage' || href === '/manage/') && (path === '/manage' || path === '/manage/' || path === '/manage/index.html')) {
            link.classList.add('active');
        }
    });

    // Mobile toggle
    const toggle = document.querySelector('.admin-mobile-toggle');
    const sidebar = document.querySelector('.admin-sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    }
}

// Logout
function setupLogout() {
    const btn = document.getElementById('logout-btn');
    if (btn) btn.addEventListener('click', async (e) => {
        e.preventDefault();
        try {
            await apiFetch('/logout', { method: 'POST' });
        } catch(e) {}
        window.location.href = '/manage/login';
    });
}

document.addEventListener('DOMContentLoaded', () => {
    setupSidebar();
    setupLogout();
});
