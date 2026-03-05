/**
 * ComfyUI Bot - Frontend Application
 * Đăng nhập, upload, WebSocket realtime, lọc, phân trang, admin.
 */

const JOBS_PER_PAGE = 10;

const state = {
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
    role: localStorage.getItem('role') || null,
    jobs: [],
    ws: null,
    selectedFile: null,
    selectedWorkflowFile: null,
    currentPage: 1,
    filters: { search: '', dateFrom: '', dateTo: '', status: '' },
};

const $ = (sel) => document.querySelector(sel);

const loginView = $('#login-view');
const dashboardView = $('#dashboard-view');
const loginForm = $('#login-form');
const loginError = $('#login-error');
const loginBtn = $('#login-btn');

const dropZone = $('#drop-zone');
const fileInput = $('#file-input');
const dropEmpty = $('#drop-zone-empty');
const dropPreview = $('#drop-zone-preview');
const previewImg = $('#preview-img');
const removeBtn = $('#remove-img');
const submitBtn = $('#submit-btn');
const jobNameInput = $('#job-name-input');
const workflowInput = $('#workflow-input');
const workflowChooseBtn = $('#workflow-choose-btn');
const workflowClearBtn = $('#workflow-clear-btn');
const workflowChooseLabel = $('#workflow-choose-label');

const jobsList = $('#jobs-list');
const jobsEmpty = $('#jobs-empty');
const jobCount = $('#job-count');
const heroTotal = $('#hero-total');
const heroRunning = $('#hero-running');
const heroDone = $('#hero-done');

const userDisplay = $('#user-display');
const userRole = $('#user-role');
const logoutBtn = $('#logout-btn');
const serverInd = $('#server-indicators');

const adminPanel = $('#admin-panel');
const adminToggle = $('#admin-toggle');
const adminContent = $('#admin-content');
const addUserForm = $('#add-user-form');
const usersList = $('#users-list');

const filterDateFrom = $('#filter-date-from');
const filterDateTo = $('#filter-date-to');
const filterStatus = $('#filter-status');
const filterSearch = $('#filter-search');
const filterClear = $('#filter-clear');
const clearListBtn = $('#clear-list-btn');
const pagination = $('#pagination');
const pagePrev = $('#page-prev');
const pageNext = $('#page-next');
const pageNumbers = $('#page-numbers');

const sidebar = $('#sidebar');
const sidebarToggle = $('#sidebar-toggle');
const mobileSidebarToggle = $('#mobile-sidebar-toggle');
const sidebarBackdrop = $('#sidebar-backdrop');
const sidebarUserName = $('#sidebar-user-name');
const sidebarUserRole = $('#sidebar-user-role');

function setSidebarCollapsed(collapsed) {
    if (!sidebar) return;
    sidebar.classList.toggle('collapsed', collapsed);
    localStorage.setItem('sidebarCollapsed', collapsed ? '1' : '0');
}

function closeMobileSidebar() {
    document.body.classList.remove('sidebar-mobile-open');
}

function openMobileSidebar() {
    document.body.classList.add('sidebar-mobile-open');
}

function syncSidebarUserInfo() {
    if (sidebarUserName) sidebarUserName.textContent = state.username || 'Người dùng';
    if (sidebarUserRole) {
        sidebarUserRole.textContent = state.role === 'admin' ? 'Quản trị viên' : 'Người dùng hệ thống';
    }
}

function initSidebarUI() {
    if (sidebar) {
        const persisted = localStorage.getItem('sidebarCollapsed') === '1';
        setSidebarCollapsed(persisted);
    }

    sidebarToggle?.addEventListener('click', () => {
        if (!sidebar) return;
        const willCollapse = !sidebar.classList.contains('collapsed');
        setSidebarCollapsed(willCollapse);
    });

    mobileSidebarToggle?.addEventListener('click', () => {
        if (document.body.classList.contains('sidebar-mobile-open')) {
            closeMobileSidebar();
        } else {
            openMobileSidebar();
        }
    });

    sidebarBackdrop?.addEventListener('click', closeMobileSidebar);

    window.addEventListener('resize', () => {
        if (window.innerWidth > 980) closeMobileSidebar();
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeMobileSidebar();
    });
}

async function api(path, options = {}) {
    const headers = { ...options.headers };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;

    const res = await fetch(path, { ...options, headers });
    if (res.status === 401) {
        logout();
        throw new Error('Phiên đăng nhập đã hết hạn');
    }
    return res;
}

function saveAuth(data) {
    state.token = data.access_token;
    state.username = data.username;
    state.role = data.role;

    localStorage.setItem('token', data.access_token);
    localStorage.setItem('username', data.username);
    localStorage.setItem('role', data.role);
}

function logout() {
    state.token = null;
    state.username = null;
    state.role = null;

    localStorage.removeItem('token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');

    if (state.ws) {
        state.ws.close();
        state.ws = null;
    }

    closeMobileSidebar();
    showLogin();
}

function showLogin() {
    if (loginView) loginView.style.display = '';
    if (dashboardView) dashboardView.style.display = 'none';
}

function showDashboard() {
    if (loginView) loginView.style.display = 'none';
    if (dashboardView) dashboardView.style.display = '';

    if (userDisplay) userDisplay.textContent = state.username || '';
    if (userRole) userRole.textContent = state.role || '';
    if (adminPanel) adminPanel.style.display = state.role === 'admin' ? '' : 'none';

    syncSidebarUserInfo();
    closeMobileSidebar();
    loadJobs();
    renderServers([]);
    connectWS();
}

loginForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (loginError) loginError.style.display = 'none';
    if (loginBtn) {
        loginBtn.querySelector('span').textContent = 'Đang đăng nhập...';
        loginBtn.querySelector('.spinner').style.display = '';
        loginBtn.disabled = true;
    }

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: $('#login-username').value.trim(),
                password: $('#login-password').value,
            }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Đăng nhập thất bại');
        }

        const data = await res.json();
        saveAuth(data);
        showDashboard();
    } catch (err) {
        if (loginError) {
            loginError.textContent = err.message;
            loginError.style.display = '';
        }
    } finally {
        if (loginBtn) {
            loginBtn.querySelector('span').textContent = 'Đăng nhập';
            loginBtn.querySelector('.spinner').style.display = 'none';
            loginBtn.disabled = false;
        }
    }
});

logoutBtn?.addEventListener('click', logout);

function updateWorkflowUI() {
    if (state.selectedWorkflowFile) {
        const fullName = state.selectedWorkflowFile.name;
        if (workflowChooseLabel) workflowChooseLabel.textContent = fullName;
        if (workflowChooseBtn) workflowChooseBtn.title = `Workflow đang chọn: ${fullName}`;
        workflowChooseBtn?.classList.add('workflow-selected');
        if (workflowClearBtn) workflowClearBtn.hidden = false;
    } else {
        if (workflowChooseLabel) workflowChooseLabel.textContent = 'Chọn workflow';
        if (workflowChooseBtn) workflowChooseBtn.title = 'Chọn workflow .json';
        workflowChooseBtn?.classList.remove('workflow-selected');
        if (workflowClearBtn) workflowClearBtn.hidden = true;
    }
}

// Upload
if (dropZone && fileInput && removeBtn && submitBtn) {
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith('image/')) selectFile(files[0]);
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) selectFile(fileInput.files[0]);
    });

    workflowChooseBtn?.addEventListener('click', () => workflowInput?.click());

    workflowInput?.addEventListener('change', () => {
        if (workflowInput.files.length > 0) {
            const picked = workflowInput.files[0];
            if (!picked.name.toLowerCase().endsWith('.json')) {
                alert('Workflow phải là file .json');
                workflowInput.value = '';
                return;
            }
            state.selectedWorkflowFile = picked;
            updateWorkflowUI();
        }
    });

    workflowClearBtn?.addEventListener('click', () => {
        state.selectedWorkflowFile = null;
        if (workflowInput) workflowInput.value = '';
        updateWorkflowUI();
    });

    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFile();
    });

    submitBtn.addEventListener('click', async () => {
        if (!state.selectedFile) return;

        submitBtn.disabled = true;
        submitBtn.querySelector('span:last-of-type').textContent = 'Đang gửi...';
        submitBtn.querySelector('.spinner').style.display = '';

        try {
            const formData = new FormData();
            formData.append('file', state.selectedFile);
            const jobName = jobNameInput?.value.trim() || '';
            if (jobName) formData.append('job_name', jobName);
            if (state.selectedWorkflowFile) {
                formData.append('workflow_file', state.selectedWorkflowFile);
            }

            const res = await api('/api/jobs', { method: 'POST', body: formData });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Gửi job thất bại');
            }

            clearFile();
            if (jobNameInput) jobNameInput.value = '';
        } catch (err) {
            alert(`Lỗi: ${err.message}`);
        } finally {
            submitBtn.querySelector('span:last-of-type').textContent = 'Tạo video';
            submitBtn.querySelector('.spinner').style.display = 'none';
            submitBtn.disabled = !state.selectedFile;
        }
    });

    updateWorkflowUI();
}

function selectFile(file) {
    state.selectedFile = file;

    const reader = new FileReader();
    reader.onload = (e) => {
        previewImg.src = e.target.result;
        dropEmpty.style.display = 'none';
        dropPreview.style.display = '';
        submitBtn.disabled = false;
    };
    reader.readAsDataURL(file);
}

function clearFile() {
    state.selectedFile = null;
    fileInput.value = '';
    previewImg.src = '';

    dropEmpty.style.display = '';
    dropPreview.style.display = 'none';
    submitBtn.disabled = true;
}

function updateHeroStats() {
    if (!heroTotal || !heroRunning || !heroDone) return;

    const total = state.jobs.length;
    const running = state.jobs.filter((j) => j.status === 'running').length;
    const done = state.jobs.filter((j) => j.status === 'done').length;

    heroTotal.textContent = String(total);
    heroRunning.textContent = String(running);
    heroDone.textContent = String(done);
}

async function loadJobs() {
    try {
        const res = await api('/api/jobs');
        if (!res.ok) return;

        state.jobs = await res.json();
        state.jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        renderJobs();
    } catch (err) {
        console.error('loadJobs error:', err);
    }
}

function getFilteredJobs() {
    let jobs = [...state.jobs];
    jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    if (state.filters.search) {
        const q = state.filters.search.toLowerCase();
        jobs = jobs.filter((j) => getJobName(j).toLowerCase().includes(q));
    }

    if (state.filters.dateFrom) {
        const from = new Date(state.filters.dateFrom);
        from.setHours(0, 0, 0, 0);
        jobs = jobs.filter((j) => new Date(j.created_at) >= from);
    }

    if (state.filters.dateTo) {
        const to = new Date(state.filters.dateTo);
        to.setHours(23, 59, 59, 999);
        jobs = jobs.filter((j) => new Date(j.created_at) <= to);
    }

    if (state.filters.status) {
        jobs = jobs.filter((j) => j.status === state.filters.status);
    }

    return jobs;
}

filterSearch?.addEventListener('input', () => {
    state.filters.search = filterSearch.value.trim();
    state.currentPage = 1;
    renderJobs();
});

filterDateFrom?.addEventListener('change', () => {
    state.filters.dateFrom = filterDateFrom.value;
    state.currentPage = 1;
    renderJobs();
});

filterDateTo?.addEventListener('change', () => {
    state.filters.dateTo = filterDateTo.value;
    state.currentPage = 1;
    renderJobs();
});

filterStatus?.addEventListener('change', () => {
    state.filters.status = filterStatus.value;
    state.currentPage = 1;
    renderJobs();
});

filterClear?.addEventListener('click', () => {
    state.filters = { search: '', dateFrom: '', dateTo: '', status: '' };
    if (filterSearch) filterSearch.value = '';
    filterDateFrom.value = '';
    filterDateTo.value = '';
    filterStatus.value = '';
    state.currentPage = 1;
    renderJobs();
});

clearListBtn?.addEventListener('click', async () => {
    try {
        const isAdmin = state.role === 'admin';
        const msg = isAdmin
            ? 'Xóa toàn bộ job list trên hệ thống?'
            : 'Xóa toàn bộ job của bạn khỏi danh sách?';
        if (!confirm(msg)) return;

        const scope = isAdmin ? 'all' : 'mine';
        const res = await api(`/api/jobs/clear?scope=${scope}`, { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Clear list thất bại');
        }

        await loadJobs();
    } catch (err) {
        alert(`Lỗi: ${err.message}`);
    }
});

function renderJobs() {
    const filtered = getFilteredJobs();
    const totalPages = Math.max(1, Math.ceil(filtered.length / JOBS_PER_PAGE));
    if (state.currentPage > totalPages) state.currentPage = totalPages;

    const start = (state.currentPage - 1) * JOBS_PER_PAGE;
    const pageJobs = filtered.slice(start, start + JOBS_PER_PAGE);

    if (jobCount) jobCount.textContent = `${filtered.length} jobs`;
    updateHeroStats();

    jobsList.querySelectorAll('.job-item').forEach((el) => el.remove());

    if (filtered.length === 0) {
        jobsEmpty.style.display = '';
        pagination.style.display = 'none';
        return;
    }

    jobsEmpty.style.display = 'none';

    pageJobs.forEach((job) => {
        const el = document.createElement('div');
        el.className = 'job-item';
        el.dataset.id = job.id;
        el.innerHTML = getJobHTML(job);
        jobsList.appendChild(el);
    });

    if (totalPages > 1) {
        pagination.style.display = '';
        renderPagination(totalPages);
    } else {
        pagination.style.display = 'none';
    }
}

function renderPagination(totalPages) {
    pagePrev.disabled = state.currentPage <= 1;
    pageNext.disabled = state.currentPage >= totalPages;

    let html = '';
    const maxVisible = 7;
    let startPage = Math.max(1, state.currentPage - 3);
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);

    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    if (startPage > 1) html += '<button class="page-btn" data-page="1">1</button>';
    if (startPage > 2) html += '<span style="color:var(--text-subtle)">...</span>';

    for (let i = startPage; i <= endPage; i += 1) {
        html += `<button class="page-btn ${i === state.currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
    }

    if (endPage < totalPages - 1) html += '<span style="color:var(--text-subtle)">...</span>';
    if (endPage < totalPages) html += `<button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;

    pageNumbers.innerHTML = html;
}

pagePrev?.addEventListener('click', () => {
    if (state.currentPage > 1) {
        state.currentPage -= 1;
        renderJobs();
    }
});

pageNext?.addEventListener('click', () => {
    const totalPages = Math.max(1, Math.ceil(getFilteredJobs().length / JOBS_PER_PAGE));
    if (state.currentPage < totalPages) {
        state.currentPage += 1;
        renderJobs();
    }
});

pageNumbers?.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-page]');
    if (!btn) return;

    state.currentPage = parseInt(btn.dataset.page, 10);
    renderJobs();
});

function getJobHTML(job) {
    const statusMap = {
        queued: { label: 'Chờ', cls: 'status-queued' },
        running: { label: 'Đang tạo', cls: 'status-running' },
        done: { label: 'Hoàn tất', cls: 'status-done' },
        error: { label: 'Lỗi', cls: 'status-error' },
        cancelled: { label: 'Đã hủy', cls: 'status-cancelled' },
    };

    const st = statusMap[job.status] || statusMap.queued;

    let progressHTML = '';
    if (job.status === 'running') {
        progressHTML = `<div class="progress-bar"><div class="progress-bar-fill" style="width:${job.progress}%"></div></div>`;
    }

    let actionsHTML = '';

    if (job.status === 'done' && (job.has_video || job.has_output)) {
        actionsHTML += `<button class="btn-download" onclick="downloadVideo('${job.id}')" title="Tải video">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>
            </svg>
            Tải
        </button>`;
    }
    if (job.status === 'done' && (job.has_image || job.has_output)) {
        actionsHTML += `<button class="btn-download" onclick="downloadImage('${job.id}')" title="Tải ảnh output">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <path d="M21 15l-5-5L5 21"/>
            </svg>
            Ảnh
        </button>`;
    }

    if (job.status !== 'running') {
        actionsHTML += `<button class="btn-delete" onclick="deleteJob('${job.id}')" title="Xóa khỏi danh sách" aria-label="Xóa job">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 6h18"/>
                <path d="M8 6V4h8v2"/>
                <path d="M19 6l-1 14H6L5 6"/>
                <path d="M10 11v6M14 11v6"/>
            </svg>
        </button>`;
    }

    if (job.status === 'error' && job.error_msg) {
        actionsHTML += `<span class="error-text" style="font-size:11px;max-width:180px;text-align:right" title="${escapeHTML(job.error_msg)}">${truncate(job.error_msg, 60)}</span>`;
    }

    const shortId = job.id.substring(0, 8);
    const time = formatTime(job.created_at);
    const showUser = state.role === 'admin' ? `<span class="job-user">${escapeHTML(job.username)}</span>` : '';
    const title = escapeHTML(getJobName(job, shortId));
    const workflowBadge = job.workflow_name
        ? `<span class="job-workflow" title="${escapeHTML(job.workflow_name)}">${escapeHTML(job.workflow_name)}</span>`
        : '';

    return `
        <img class="job-thumb" src="/api/jobs/${job.id}/thumbnail" alt="" loading="lazy" onerror="this.style.display='none'">
        <div class="job-info">
            <p class="job-title" title="${title}">${title}</p>
            <div class="job-info-top">
                <span class="job-id">#${shortId}</span>
                <span class="job-server">${escapeHTML(job.server_name || 'N/A')}</span>
                ${workflowBadge}
                ${showUser}
                <span class="status-badge ${st.cls}">${st.label}</span>
            </div>
            <span class="job-time">${time}${job.status === 'running' ? ` · ${job.progress}%` : ''}</span>
            ${progressHTML}
        </div>
        <div class="job-actions">
            ${actionsHTML}
        </div>
    `;
}

async function deleteJob(jobId) {
    try {
        const res = await api(`/api/jobs/${jobId}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Xóa thất bại');
        }

        state.jobs = state.jobs.filter((j) => j.id !== jobId);
        renderJobs();
    } catch (err) {
        alert(`Lỗi: ${err.message}`);
    }
}
window.deleteJob = deleteJob;

function downloadVideo(jobId) {
    const job = state.jobs.find((j) => j.id === jobId);
    const baseName = sanitizeFilename(getJobName(job, jobId.substring(0, 8)));

    fetch(`/api/jobs/${jobId}/video?token=${encodeURIComponent(state.token)}`)
        .then((res) => {
            if (!res.ok) throw new Error('Tải video thất bại');
            return res.blob();
        })
        .then((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${baseName}.mp4`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        })
        .catch((err) => alert(`Lỗi tải video: ${err.message}`));
}
window.downloadVideo = downloadVideo;

function downloadImage(jobId) {
    const job = state.jobs.find((j) => j.id === jobId);
    const baseName = sanitizeFilename(getJobName(job, jobId.substring(0, 8)));

    fetch(`/api/jobs/${jobId}/image?token=${encodeURIComponent(state.token)}`)
        .then((res) => {
            if (!res.ok) throw new Error('Tải ảnh thất bại');
            const contentType = res.headers.get('content-type') || '';
            let ext = '.png';
            if (contentType.includes('jpeg') || contentType.includes('jpg')) ext = '.jpg';
            if (contentType.includes('webp')) ext = '.webp';
            return res.blob().then((blob) => ({ blob, ext }));
        })
        .then(({ blob, ext }) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${baseName}${ext}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        })
        .catch((err) => alert(`Lỗi tải ảnh: ${err.message}`));
}
window.downloadImage = downloadImage;

function connectWS() {
    if (state.ws) state.ws.close();

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/ws/jobs?token=${state.token}`;
    state.ws = new WebSocket(url);

    state.ws.onopen = () => console.log('WS connected');

    state.ws.onmessage = (event) => {
        try {
            handleWSMessage(JSON.parse(event.data));
        } catch (err) {
            console.error('WS parse error:', err);
        }
    };

    state.ws.onclose = () => {
        console.log('WS disconnected - reconnecting in 3s...');
        setTimeout(() => {
            if (state.token) connectWS();
        }, 3000);
    };

    state.ws.onerror = (err) => console.error('WS error:', err);
}

function handleWSMessage(data) {
    if (data.type === 'job_update') {
        const job = data.job;
        const idx = state.jobs.findIndex((j) => j.id === job.id);
        if (idx >= 0) {
            state.jobs[idx] = job;
        } else {
            state.jobs.unshift(job);
        }

        state.jobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        renderJobs();
    }

    if (data.type === 'servers_status') {
        renderServers(data.servers);
    }
}

function renderServers(servers) {
    if (!serverInd) return;

    const incoming = Array.isArray(servers) ? servers : [];

    const normalizeName = (name = '') => String(name).trim().toLowerCase();

    const defaults = [
        { name: 'GPU #1', status: 'offline' },
        { name: 'GPU #2', status: 'offline' },
    ];

    const byName = new Map();

    defaults.forEach((s) => {
        byName.set(normalizeName(s.name), s);
    });

    incoming.forEach((s) => {
        const normalized = normalizeName(s?.name);
        if (!normalized) return;

        let canonicalName = s.name;
        if (normalized.includes('gpu #1') || normalized.includes('gpu1')) canonicalName = 'GPU #1';
        if (normalized.includes('gpu #2') || normalized.includes('gpu2')) canonicalName = 'GPU #2';

        byName.set(normalizeName(canonicalName), {
            name: canonicalName,
            status: s?.status || 'offline',
        });
    });

    const primaryOrder = ['gpu #1', 'gpu #2'];
    const ordered = [
        ...primaryOrder
            .map((key) => byName.get(key))
            .filter(Boolean),
        ...Array.from(byName.entries())
            .filter(([key]) => !primaryOrder.includes(key))
            .map(([, value]) => value),
    ];

    serverInd.innerHTML = ordered
        .map(
            (s) => `
            <div class="server-dot ${s.status}" title="${escapeHTML(s.name)}: ${escapeHTML(s.status)}">
                <span class="dot"></span>
                <span>${escapeHTML(s.name)}</span>
            </div>
        `
        )
        .join('');
}

adminToggle?.addEventListener('click', () => {
    const visible = adminContent.style.display === 'none';
    adminContent.style.display = visible ? '' : 'none';
    if (visible) loadUsers();
});

addUserForm?.addEventListener('submit', async (e) => {
    e.preventDefault();

    try {
        const res = await api('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: $('#new-username').value.trim(),
                password: $('#new-password').value,
                role: $('#new-role').value,
            }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Thêm người dùng thất bại');
        }

        $('#new-username').value = '';
        $('#new-password').value = '';
        loadUsers();
    } catch (err) {
        alert(`Lỗi: ${err.message}`);
    }
});

async function loadUsers() {
    try {
        const res = await api('/api/auth/users');
        if (!res.ok) return;

        const users = await res.json();
        usersList.innerHTML = users
            .map(
                (u) => `
                <div class="user-item">
                    <span>${escapeHTML(u.username)}</span>
                    <span class="role-badge">${escapeHTML(u.role)}</span>
                </div>
            `
            )
            .join('');
    } catch (err) {
        console.error('loadUsers error:', err);
    }
}

function sanitizeFilename(str) {
    return String(str || 'job')
        .trim()
        .replace(/[<>:"/\\|?*\x00-\x1F]/g, '_')
        .replace(/\s+/g, '_')
        .replace(/_+/g, '_')
        .slice(0, 120) || 'job';
}

function getJobName(job, fallback = '') {
    if (!job) return fallback ? `job_${fallback}` : 'job';
    const raw = job.job_name || job.video_name || '';
    if (raw) return String(raw);
    return fallback ? `job_${fallback}` : 'job';
}

function escapeHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? `${str.substring(0, len)}...` : str;
}

function formatTime(ts) {
    if (!ts) return '';

    try {
        const d = new Date(ts);
        if (Number.isNaN(d.getTime())) return ts;

        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        const mo = String(d.getMonth() + 1).padStart(2, '0');
        const yy = d.getFullYear();

        return `${hh}:${mm} ${dd}/${mo}/${yy}`;
    } catch {
        return ts;
    }
}

initSidebarUI();

if (state.token) {
    showDashboard();
} else {
    showLogin();
}





