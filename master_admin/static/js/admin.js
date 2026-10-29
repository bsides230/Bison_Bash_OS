function showToast(message, type = 'error') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerText = message;
    document.body.appendChild(toast);

    setTimeout(() => { toast.classList.add('show'); }, 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

let manifestData = [];

async function pollProcessStatus() {
    try {
        const res = await fetch('/api/process/status');
        const data = await res.json();
        if (data.status === 'success' && data.processes) {
            for (const [gid, p] of Object.entries(data.processes)) {
                const el = document.getElementById(`status-${gid}`);
                if (el) {
                    if (p.running) {
                        el.className = 'status-badge status-running';
                        el.innerText = `Running (PID ${p.pid})`;
                    } else {
                        el.className = 'status-badge status-stopped';
                        el.innerText = 'Stopped';
                    }
                }
            }
        }
    } catch(e) {}
}

async function startProcess(gameId) {
    try {
        const res = await fetch('/api/process/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId})
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`Started ${gameId}`, 'success');
        } else {
            showToast(`Failed to start ${gameId}`, 'error');
        }
        pollProcessStatus();
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function stopProcess(gameId) {
    try {
        const res = await fetch('/api/process/stop', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId})
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`Stopped ${gameId}`, 'success');
        }
        pollProcessStatus();
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function loadAdminManifest() {
    try {
        const res = await fetch('/api/players/manifest');
        const data = await res.json();
        if (data.status === 'success') {
            manifestData = data.players || [];
            renderAdminManifest(manifestData);
            renderSimpleManifest(manifestData);
        }
    } catch(e) {}
}

function openManifestModal() {
    loadAdminManifest();
    const modal = document.getElementById('manifest-modal');
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeManifestModal() {
    const modal = document.getElementById('manifest-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

/* ==========================================================
   ATTENDEE EMAIL TEMPLATE CONFIGURATION (WEB / MOBILE ADMIN)
   ========================================================== */
let cachedEmailConfig = null;

async function openEmailConfigModal() {
    const modal = document.getElementById('email-config-modal');
    if (!modal) return;

    try {
        const res = await fetch('/api/email/config');
        if (res.ok) {
            const data = await res.json();
            cachedEmailConfig = data.config || {};
            const enabledInput = document.getElementById('email-cfg-enabled');
            const subjectInput = document.getElementById('email-cfg-subject');
            const bodyInput = document.getElementById('email-cfg-body');

            if (enabledInput) enabledInput.checked = Boolean(cachedEmailConfig.enabled);
            if (subjectInput) subjectInput.value = cachedEmailConfig.subject_template || "Your Bison Bash Player Pass & 4-Digit PIN";
            if (bodyInput) bodyInput.value = cachedEmailConfig.body_template || (
                "Hi {name},\n\n" +
                "Welcome to Bison Bash! Here is your digital venue pass:\n\n" +
                "----------------------------------------\n" +
                "YOUR 4-DIGIT PIN: {pin}\n" +
                "STARTING BALANCE: {balance} Credits\n" +
                "----------------------------------------\n\n" +
                "Punch this 4-digit PIN into any betting kiosk, N64 tournament station, or game booth on the venue floor to play.\n\n" +
                "See you at the races!\n" +
                "The Techlahoma Team"
            );
            updateEmailLivePreview();
        }
    } catch(err) {
        console.warn("Could not load email configuration:", err);
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeEmailConfigModal() {
    const modal = document.getElementById('email-config-modal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

function insertTokenToBody(token) {
    const bodyInput = document.getElementById('email-cfg-body');
    if (!bodyInput) return;
    const start = bodyInput.selectionStart || 0;
    const end = bodyInput.selectionEnd || 0;
    const val = bodyInput.value;
    bodyInput.value = val.substring(0, start) + token + val.substring(end);
    bodyInput.focus();
    bodyInput.selectionStart = bodyInput.selectionEnd = start + token.length;
    updateEmailLivePreview();
}

function updateEmailLivePreview() {
    const subjectInput = document.getElementById('email-cfg-subject');
    const bodyInput = document.getElementById('email-cfg-body');
    const prevSubject = document.getElementById('email-preview-subject');
    const prevBody = document.getElementById('email-preview-body');

    const sampleName = "Jane Doe";
    const samplePin = "4821";
    const sampleBal = "100";

    if (subjectInput && prevSubject) {
        let s = subjectInput.value || "";
        s = s.replace(/\{name\}/g, sampleName)
             .replace(/\{pin\}/g, samplePin)
             .replace(/\{balance\}/g, sampleBal);
        prevSubject.innerText = s ? `Subject: ${s}` : `Subject: (Empty Subject)`;
    }

    if (bodyInput && prevBody) {
        let b = bodyInput.value || "";
        b = b.replace(/\{name\}/g, sampleName)
             .replace(/\{pin\}/g, samplePin)
             .replace(/\{balance\}/g, sampleBal);
        prevBody.innerText = b;
    }
}

async function saveEmailConfigFromModal() {
    const enabledInput = document.getElementById('email-cfg-enabled');
    const subjectInput = document.getElementById('email-cfg-subject');
    const bodyInput = document.getElementById('email-cfg-body');
    const btn = document.getElementById('btn-save-email-cfg');

    if (btn) {
        btn.disabled = true;
        btn.innerText = "Saving...";
    }

    const payload = {
        enabled: enabledInput ? enabledInput.checked : false,
        subject_template: subjectInput ? subjectInput.value.trim() : "",
        body_template: bodyInput ? bodyInput.value : ""
    };

    try {
        const res = await fetch('/api/email/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            showToast("✅ Email template saved successfully!");
            setTimeout(closeEmailConfigModal, 400);
        } else {
            const err = await res.json();
            showToast("❌ Failed to save: " + (err.message || res.statusText));
        }
    } catch(err) {
        showToast("❌ Network error saving email template.");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = "💾 Save Email Template";
        }
    }
}

function renderSimpleManifest(list) {
    const container = document.getElementById('simple-manifest-list');
    const summaryText = document.getElementById('manifest-summary-text');
    if (!container) return;
    container.innerHTML = '';

    const total = manifestData.reduce((acc, p) => acc + (p.balance || 0), 0);
    if (summaryText) {
        summaryText.innerText = `${manifestData.length} Attendees Registered • 🪙 ${total.toLocaleString()} Total Tokens`;
    }

    if (list.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: #8b949e; padding: 20px;">No registered players found.</div>`;
        return;
    }

    list.forEach(p => {
        const item = document.createElement('div');
        item.className = 'manifest-player-item';
        item.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px;">
                <span class="player-pin-pill">${p.pin || '—'}</span>
                <div>
                    <strong style="color: #fff; font-size: 0.95rem;">${p.name || p.id}</strong>
                    ${p.email ? `<div style="font-size: 0.76rem; color: #8b949e;">${p.email}</div>` : ''}
                </div>
            </div>
            <div>
                <span class="player-bal-pill">🪙 ${p.balance ?? 0}</span>
            </div>
        `;
        container.appendChild(item);
    });
}

function filterSimpleManifest() {
    const searchInput = document.getElementById('manifest-search-simple');
    if (!searchInput) return;
    const q = searchInput.value.toLowerCase().trim();
    if (!q) {
        renderSimpleManifest(manifestData);
        return;
    }
    const filtered = manifestData.filter(p => 
        (p.name && p.name.toLowerCase().includes(q)) ||
        (p.email && p.email.toLowerCase().includes(q)) ||
        (p.id && p.id.toLowerCase().includes(q)) ||
        (p.pin && String(p.pin).includes(q))
    );
    renderSimpleManifest(filtered);
}

function renderAdminManifest(list) {
    const tbody = document.getElementById('admin-manifest-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    const countEl = document.getElementById('stat-player-count');
    const tokensEl = document.getElementById('stat-total-tokens');
    if (countEl) countEl.innerText = manifestData.length;
    if (tokensEl) {
        const total = manifestData.reduce((acc, p) => acc + (p.balance || 0), 0);
        tokensEl.innerText = total.toLocaleString();
    }

    if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 20px;">No registered attendees found.</td></tr>`;
        return;
    }

    list.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${p.name || p.id}</strong></td>
            <td><span class="player-pin-badge">${p.pin || '—'}</span></td>
            <td style="color: var(--text-secondary); font-size: 0.8rem;">${p.email || '—'}</td>
            <td style="font-family: monospace; font-size: 0.75rem; color: var(--text-secondary);">${p.id}</td>
            <td><span class="player-balance-pill">🪙 ${p.balance || 0}</span></td>
            <td style="font-family: monospace;">${p.total_wagers || 0}</td>
            <td>
                <div class="quick-adjust-group">
                    <button type="button" class="btn-adjust" style="color: #00ffcc;" onclick="adjustPlayer('${p.id}', 10)">+10</button>
                    <button type="button" class="btn-adjust" style="color: #ffd700;" onclick="adjustPlayer('${p.id}', 50)">+50</button>
                    <button type="button" class="btn-adjust" style="color: #ff5555;" onclick="adjustPlayer('${p.id}', -10)">-10</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function filterManifest() {
    const searchInput = document.getElementById('manifest-search');
    if (!searchInput) return;
    const q = searchInput.value.toLowerCase().trim();
    if (!q) {
        renderAdminManifest(manifestData);
        return;
    }
    const filtered = manifestData.filter(p => 
        (p.name && p.name.toLowerCase().includes(q)) ||
        (p.email && p.email.toLowerCase().includes(q)) ||
        (p.id && p.id.toLowerCase().includes(q)) ||
        (p.pin && String(p.pin).includes(q))
    );
    renderAdminManifest(filtered);
}

async function adjustPlayer(playerId, delta) {
    try {
        const res = await fetch('/api/players/adjust-balance', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({player_id: playerId, delta: delta})
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`Adjusted ${playerId} balance. New: ${data.player.balance}`, 'success');
            loadAdminManifest();
        }
    } catch(e) {
        showToast(`Failed to adjust balance: ${e.message}`, 'error');
    }
}

async function injectTokens() {
    const pid = document.getElementById('player-id').value.trim();
    const amt = parseInt(document.getElementById('token-amount').value);
    if (!pid || isNaN(amt)) return alert("Please enter valid Player ID and Amount");

    try {
        const res = await fetch('/api/admin/inject-tokens', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({player_id: pid, amount: amt})
        });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();
        showToast(`Tokens injected. New balance for ${pid}: ${data.new_balance}`, 'success');
        document.getElementById('token-amount').value = '';
        loadAdminManifest();
    } catch(e) {
        showToast(`Error injecting tokens: ${e.message}`, 'error');
    }
}

function showSignupQr() {
    const port = '8009';
    const url = `${window.location.protocol}//${window.location.hostname}:${port}/`;
    document.getElementById('signup-url-display').innerText = url;
    const target = document.getElementById('signup-qr-target');
    target.innerHTML = '';

    new QRCode(target, {
        text: url,
        width: 220,
        height: 220
    });

    document.getElementById('signup-qr-modal').style.display = 'flex';
}

function closeSignupQr() {
    document.getElementById('signup-qr-modal').style.display = 'none';
}

// --- EVENT QR CODE GENERATOR & PRINT CENTER LOGIC ---
const QR_PRESETS = {
    portal: {
        port: '8009',
        path: '/portal',
        title: 'Mobile Player Portal',
        subtitle: 'Scan with phone camera to view wallet balance & pass'
    },
    signup: {
        port: '8009',
        path: '/signup',
        title: 'Attendee Sign-Up',
        subtitle: 'Register now to receive starter tokens & your 4-digit PIN'
    },
    pass: {
        port: '8009',
        path: '/pass',
        title: 'Player Pass Lookup',
        subtitle: 'Enter your 4-digit PIN to show your digital badge'
    },
    kiosk1: {
        port: '8008',
        path: '/kiosk?tablet=1',
        title: 'Bison Dash Betting Tablet 1',
        subtitle: 'Self-service touchscreen terminal for live race wagers'
    },
    kiosk2: {
        port: '8008',
        path: '/kiosk?tablet=2',
        title: 'Bison Dash Betting Tablet 2',
        subtitle: 'Self-service touchscreen terminal for live race wagers'
    },
    gauntlet: {
        port: '8007',
        path: '/',
        title: 'AI Gauntlet Challenge',
        subtitle: 'Test your nerve in the neural gateway challenge'
    },
    mint: {
        port: '8005',
        path: '/',
        title: 'Token Mint & Cash Desk',
        subtitle: 'Volunteer station to add donation tokens to player wallets'
    },
    n64: {
        port: '8004',
        path: '/',
        title: 'N64 Arena Match Deck',
        subtitle: 'Mario Kart & GoldenEye 1v1 tournament station'
    },
    bughunt: {
        port: '8003',
        path: '/',
        title: 'Bug Bounty: Alpha Critical',
        subtitle: 'Physical 60-second bug collection challenge for kids'
    },
    bison_arena: {
        port: '8001',
        path: '/',
        title: 'Bison Dash Stadium Arena',
        subtitle: 'Main race track display and betting odds board'
    },
    bison_projector: {
        port: '8001',
        path: '/projector',
        title: 'Bison Dash Stadium Projector',
        subtitle: 'Jumbotron stadium broadcast screen'
    },
    slideshow: {
        port: '8010',
        path: '/slideshow',
        title: 'Stadium Slideshow',
        subtitle: 'Full-screen projector slideshow and live race cut-in display'
    },
    presenter: {
        port: '8010',
        path: '/presenter',
        title: 'Presenter Slide Remote',
        subtitle: 'Mobile remote control to advance presentation slides'
    },
    manifest: {
        port: '8000',
        path: '/manifest',
        title: 'Full Player Manifest',
        subtitle: 'Master roster of all registered attendees & PINs'
    },
    master_admin: {
        port: '8000',
        path: '/',
        title: 'Master Admin Venue Command',
        subtitle: 'Central operations console for all event servers'
    },
    custom: {
        port: '',
        path: '',
        title: 'Custom Event Link',
        subtitle: 'Scan to open event station'
    }
};

let currentQrCodeInstance = null;

function openQrGeneratorModal() {
    const hostInput = document.getElementById('qr-host-input');
    if (!hostInput.value) {
        hostInput.value = window.location.hostname || '127.0.0.1';
    }
    document.getElementById('qr-preset-select').value = 'portal';
    onQrPresetChange();
    document.getElementById('qr-generator-modal').style.display = 'flex';
}

function closeQrGeneratorModal() {
    document.getElementById('qr-generator-modal').style.display = 'none';
}

function onQrPresetChange() {
    const sel = document.getElementById('qr-preset-select').value;
    const cfg = QR_PRESETS[sel] || QR_PRESETS.portal;
    const host = document.getElementById('qr-host-input').value.trim() || window.location.hostname || '127.0.0.1';

    if (sel === 'custom') {
        document.getElementById('qr-url-input').readOnly = false;
        if (!document.getElementById('qr-url-input').value) {
            document.getElementById('qr-url-input').value = `${window.location.protocol}//${host}:8000/`;
        }
    } else {
        document.getElementById('qr-url-input').readOnly = false;
        const proto = window.location.protocol || 'http:';
        document.getElementById('qr-url-input').value = `${proto}//${host}:${cfg.port}${cfg.path}`;
    }

    document.getElementById('qr-title-input').value = cfg.title;
    document.getElementById('qr-subtitle-input').value = cfg.subtitle;

    updatePlacardPreview();
    regenerateQrCode();
}

function updatePlacardPreview() {
    const title = document.getElementById('qr-title-input').value;
    const subtitle = document.getElementById('qr-subtitle-input').value;

    document.getElementById('qr-preview-title').innerText = title;
    document.getElementById('qr-preview-subtitle').innerText = subtitle;
    document.getElementById('print-placard-title').innerText = title;
    document.getElementById('print-placard-subtitle').innerText = subtitle;
}

function regenerateQrCode(fromCustomUrl = false) {
    let url = document.getElementById('qr-url-input').value.trim();
    if (!fromCustomUrl) {
        const sel = document.getElementById('qr-preset-select').value;
        const cfg = QR_PRESETS[sel];
        if (cfg && sel !== 'custom') {
            const host = document.getElementById('qr-host-input').value.trim() || window.location.hostname || '127.0.0.1';
            const proto = window.location.protocol || 'http:';
            url = `${proto}//${host}:${cfg.port}${cfg.path}`;
            document.getElementById('qr-url-input').value = url;
        }
    }

    document.getElementById('qr-preview-url').innerText = url;
    document.getElementById('print-placard-url').innerText = url;

    // Render Preview QR (240x240)
    const target = document.getElementById('qr-code-display-box');
    if (target) {
        target.innerHTML = '';
        currentQrCodeInstance = new QRCode(target, {
            text: url || 'http://127.0.0.1:8000/',
            width: 240,
            height: 240,
            colorDark: '#000000',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.H
        });
    }

    // Render Print Placard QR (320x320)
    const printTarget = document.getElementById('print-placard-qr');
    if (printTarget) {
        printTarget.innerHTML = '';
        new QRCode(printTarget, {
            text: url || 'http://127.0.0.1:8000/',
            width: 320,
            height: 320,
            colorDark: '#000000',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.H
        });
    }
}

// --- FINALIZED LINKS & INSTANT QR BRING-UP LOGIC ---

let finalizedLinksData = [];

function getVenueHost() {
    const input = document.getElementById('qr-host-input');
    if (input && input.value.trim()) return input.value.trim();
    return window.location.hostname || '127.0.0.1';
}

function resolveLinkUrl(link) {
    if (link.url && (link.url.startsWith('http://') || link.url.startsWith('https://'))) {
        return link.url;
    }
    const host = getVenueHost();
    const proto = window.location.protocol || 'http:';
    const port = link.port ? `:${link.port}` : '';
    const path = link.path || '/';
    return `${proto}//${host}${port}${path}`;
}

async function loadFinalizedLinks() {
    try {
        const res = await fetch('/api/links');
        const data = await res.json();
        if (data.status === 'success' && data.links && data.links.length > 0) {
            finalizedLinksData = data.links;
        }
    } catch(e) {
        console.warn('Could not load links from server, using presets:', e);
    }

    if (!finalizedLinksData || finalizedLinksData.length === 0) {
        finalizedLinksData = Object.entries(QR_PRESETS).filter(([k]) => k !== 'custom').map(([k, v]) => ({
            id: k,
            title: v.title,
            subtitle: v.subtitle,
            port: v.port ? parseInt(v.port) : 8000,
            path: v.path || '/',
            icon: '📱',
            is_custom: false
        }));
    }

    renderFinalizedLinksGrid();
}

function renderFinalizedLinksGrid() {
    const grid = document.getElementById('finalized-links-grid');
    if (!grid) return;
    grid.innerHTML = '';

    finalizedLinksData.forEach(link => {
        const url = resolveLinkUrl(link);
        const card = document.createElement('div');
        card.className = 'qr-link-card';
        card.innerHTML = `
            <div class="qr-link-info">
                <h4>${link.icon || '📱'} ${link.title}</h4>
                <p>${link.subtitle || ''}</p>
            </div>
            <div class="qr-link-url">${url}</div>
            <div style="display: flex; gap: 8px;">
                <button type="button" class="action-btn btn-cyan" style="flex: 2; padding: 10px; font-size: 0.88rem;" onclick="bringUpQrForLink('${link.title.replace(/'/g, "\\'")}', '${(link.subtitle || '').replace(/'/g, "\\'")}', '${url}')">
                    📱 Bring Up QR Code
                </button>
                <button type="button" class="action-btn" style="flex: 1; padding: 10px; font-size: 0.85rem;" onclick="copyToClipboard('${url}')">
                    📋 Copy
                </button>
                ${link.is_custom ? `<button type="button" class="btn-mini btn-stop" style="padding: 6px 10px; font-weight:bold;" title="Delete Link" onclick="deleteCustomLink('${link.id}')">✕</button>` : ''}
            </div>
        `;
        grid.appendChild(card);
    });
}

function bringUpQrForLink(title, subtitle, url) {
    const titleInput = document.getElementById('qr-title-input');
    const subtitleInput = document.getElementById('qr-subtitle-input');
    const urlInput = document.getElementById('qr-url-input');

    if (titleInput) titleInput.value = title;
    if (subtitleInput) subtitleInput.value = subtitle;
    if (urlInput) urlInput.value = url;

    const previewTitle = document.getElementById('qr-preview-title');
    const previewSubtitle = document.getElementById('qr-preview-subtitle');
    const previewUrl = document.getElementById('qr-preview-url');

    if (previewTitle) previewTitle.innerText = title;
    if (previewSubtitle) previewSubtitle.innerText = subtitle;
    if (previewUrl) previewUrl.innerText = url;

    const placardTitle = document.getElementById('print-placard-title');
    const placardSubtitle = document.getElementById('print-placard-subtitle');
    const placardUrl = document.getElementById('print-placard-url');

    if (placardTitle) placardTitle.innerText = title;
    if (placardSubtitle) placardSubtitle.innerText = subtitle;
    if (placardUrl) placardUrl.innerText = url;

    // Render Preview QR (240x240)
    const target = document.getElementById('qr-code-display-box');
    if (target) {
        target.innerHTML = '';
        currentQrCodeInstance = new QRCode(target, {
            text: url || 'http://127.0.0.1:8000/',
            width: 240,
            height: 240,
            colorDark: '#000000',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.H
        });
    }

    // Render Print Placard QR (320x320)
    const printTarget = document.getElementById('print-placard-qr');
    if (printTarget) {
        printTarget.innerHTML = '';
        new QRCode(printTarget, {
            text: url || 'http://127.0.0.1:8000/',
            width: 320,
            height: 320,
            colorDark: '#000000',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.H
        });
    }

    const modal = document.getElementById('qr-generator-modal');
    if (modal) modal.style.display = 'flex';
}

function bringUpCustomFormQr() {
    const title = document.getElementById('custom-link-title').value.trim() || 'Custom Event Link';
    let url = document.getElementById('custom-link-url').value.trim();
    const subtitle = document.getElementById('custom-link-subtitle').value.trim() || 'Scan with phone camera to open';

    if (!url) return alert('Please enter a destination URL first.');
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'http://' + url;
    }

    bringUpQrForLink(title, subtitle, url);
}

async function saveCustomFormLink() {
    const title = document.getElementById('custom-link-title').value.trim();
    let url = document.getElementById('custom-link-url').value.trim();
    const subtitle = document.getElementById('custom-link-subtitle').value.trim() || 'Scan with phone camera to open';

    if (!title) return alert('Please enter a link title.');
    if (!url) return alert('Please enter a destination URL.');

    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'http://' + url;
    }

    try {
        const res = await fetch('/api/links', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                title: title,
                url: url,
                subtitle: subtitle,
                is_custom: true,
                icon: '🔗'
            })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`Saved link: ${title}`, 'success');
            document.getElementById('custom-link-title').value = '';
            document.getElementById('custom-link-url').value = '';
            document.getElementById('custom-link-subtitle').value = '';
            loadFinalizedLinks();
        }
    } catch(e) {
        showToast(`Error saving link: ${e.message}`, 'error');
    }
}

async function deleteCustomLink(id) {
    if (!confirm('Delete this finalized link?')) return;
    try {
        const res = await fetch(`/api/links/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('Link removed', 'success');
            loadFinalizedLinks();
        }
    } catch(e) {
        showToast('Error removing link', 'error');
    }
}

function applyHostIpToAll() {
    const host = getVenueHost();
    showToast(`Applied host IP: ${host}`, 'success');
    renderFinalizedLinksGrid();
    updateDjUrlDisplay();
    updatePresenterUrlDisplay();
}

function onHostIpChange() {
    renderFinalizedLinksGrid();
    updateDjUrlDisplay();
    updatePresenterUrlDisplay();
}

function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('Copied link to clipboard!', 'success');
        }).catch(() => fallbackCopy(text));
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const el = document.createElement('textarea');
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    showToast('Copied link to clipboard!', 'success');
}

function copyQrUrl() {
    const url = document.getElementById('qr-url-input').value;
    copyToClipboard(url);
}

function downloadQrPng(dimension = 1024) {
    const url = document.getElementById('qr-url-input').value;
    const title = document.getElementById('qr-title-input').value.replace(/[^a-zA-Z0-9_-]/g, '_');
    const filename = `QR_${title || 'Code'}.png`;

    // Render offscreen canvas with high resolution (1024x1024 for slides)
    const offscreen = document.createElement('div');
    offscreen.style.position = 'absolute';
    offscreen.style.left = '-99999px';
    offscreen.style.top = '-99999px';
    document.body.appendChild(offscreen);

    new QRCode(offscreen, {
        text: url,
        width: dimension,
        height: dimension,
        colorDark: '#000000',
        colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.H
    });

    setTimeout(() => {
        const canvas = offscreen.querySelector('canvas');
        let dataUrl = '';
        if (canvas) {
            dataUrl = canvas.toDataURL('image/png');
        } else {
            const img = offscreen.querySelector('img');
            if (img) dataUrl = img.src;
        }

        if (dataUrl) {
            const a = document.createElement('a');
            a.download = filename;
            a.href = dataUrl;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast(`Downloaded ${filename} (${dimension}x${dimension})!`, 'success');
        } else {
            showToast('Error generating high-res PNG download', 'error');
        }
        document.body.removeChild(offscreen);
    }, 200);
}

function printQrPlacard() {
    window.print();
}

// --- ECONOMY RULES MODAL LOGIC ---
async function openEconomyModal() {
    switchTab('economy');
    try {
        const res = await fetch('/api/economy/config');
        const data = await res.json();
        if (data.status === 'success' && data.config) {
            const cfg = data.config;
            const initEl = document.getElementById('eco-initial-allotment');
            if (initEl) initEl.value = cfg.initial_allotment ?? 100;

            const costs = cfg.costs || {};
            const cN64 = document.getElementById('eco-cost-n64');
            const cBug = document.getElementById('eco-cost-bughunt');
            const cGau = document.getElementById('eco-cost-gauntlet');
            const cMin = document.getElementById('eco-cost-bison-min-bet');
            if (cN64) cN64.value = costs.n64 ?? 0;
            if (cBug) cBug.value = costs.bughunt ?? 0;
            if (cGau) cGau.value = costs.gauntlet ?? 0;
            if (cMin) cMin.value = costs.bison_dash_min_bet ?? 5;

            const payouts = cfg.payouts || {};
            const pN64 = document.getElementById('eco-payout-n64');
            const pMul = document.getElementById('eco-payout-bison-mult');
            const pRat = document.getElementById('eco-payout-bughunt-ratio');
            const pPit = document.getElementById('eco-payout-bughunt-pity');
            if (pN64) pN64.value = payouts.n64_winner ?? 10;
            if (pMul) pMul.value = payouts.bison_dash_multiplier ?? 2.0;
            if (pRat) pRat.value = payouts.bughunt_bugs_per_token ?? 5;
            if (pPit) pPit.value = payouts.bughunt_pity_tokens ?? 1;

            const gaunt = payouts.gauntlet || {};
            const g1 = document.getElementById('eco-gauntlet-s1');
            const g2 = document.getElementById('eco-gauntlet-s2');
            const g3 = document.getElementById('eco-gauntlet-s3');
            const g4 = document.getElementById('eco-gauntlet-s4');
            const gj = document.getElementById('eco-gauntlet-jackpot');
            const gr = document.getElementById('eco-gauntlet-runner-up');
            if (g1) g1.value = gaunt.stage1 ?? 2;
            if (g2) g2.value = gaunt.stage2 ?? 3;
            if (g3) g3.value = gaunt.stage3 ?? 5;
            if (g4) g4.value = gaunt.stage4 ?? 8;
            if (gj) gj.value = gaunt.vault_jackpot ?? 25;
            if (gr) gr.value = gaunt.vault_runner_up ?? 10;
        } else {
            showToast("Failed to load economy configuration", "error");
        }
    } catch (e) {
        showToast(`Error loading economy config: ${e.message}`, "error");
    }
}

function closeEconomyModal() {
    const modal = document.getElementById('economy-modal');
    if (modal) modal.style.display = 'none';
}

async function saveEconomyConfig() {
    const payload = {
        initial_allotment: parseInt(document.getElementById('eco-initial-allotment').value) || 100,
        costs: {
            n64: parseInt(document.getElementById('eco-cost-n64').value) || 0,
            bughunt: parseInt(document.getElementById('eco-cost-bughunt').value) || 0,
            gauntlet: parseInt(document.getElementById('eco-cost-gauntlet').value) || 0,
            bison_dash_min_bet: parseInt(document.getElementById('eco-cost-bison-min-bet').value) || 5
        },
        payouts: {
            n64_winner: parseInt(document.getElementById('eco-payout-n64').value) || 10,
            bughunt_bugs_per_token: parseInt(document.getElementById('eco-payout-bughunt-ratio').value) || 5,
            bughunt_pity_tokens: parseInt(document.getElementById('eco-payout-bughunt-pity').value) || 1,
            gauntlet: {
                stage1: parseInt(document.getElementById('eco-gauntlet-s1').value) || 2,
                stage2: parseInt(document.getElementById('eco-gauntlet-s2').value) || 3,
                stage3: parseInt(document.getElementById('eco-gauntlet-s3').value) || 5,
                stage4: parseInt(document.getElementById('eco-gauntlet-s4').value) || 8,
                vault_jackpot: parseInt(document.getElementById('eco-gauntlet-jackpot').value) || 25,
                vault_runner_up: parseInt(document.getElementById('eco-gauntlet-runner-up').value) || 10
            },
            bison_dash_multiplier: parseFloat(document.getElementById('eco-payout-bison-mult').value) || 2.0
        }
    };

    try {
        const res = await fetch('/api/economy/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast("✓ Economy rules saved! Live across all stations.", "success");
            closeEconomyModal();
        } else {
            showToast(`Save failed: ${data.message || 'Unknown error'}`, "error");
        }
    } catch (e) {
        showToast(`Network error: ${e.message}`, "error");
    }
}

async function resetEconomyDefaults() {
    if (!confirm("Are you sure you want to restore default payouts and costs?")) return;
    try {
        const res = await fetch('/api/economy/reset', {
            method: 'POST'
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast("Economy restored to factory defaults", "success");
            openEconomyModal();
        } else {
            showToast("Failed to reset economy", "error");
        }
    } catch (e) {
        showToast(`Error resetting economy: ${e.message}`, "error");
    }
}

// =========================================================================
// SLIDESHOW & BISON DASH SCREEN MANAGER LOGIC
// =========================================================================

let slideshowPollTimer = null;
let currentSlidesDeck = [];
let currentPresentationDeck = [];

function openSlideshowModal() {
    switchTab('slideshow');
    updateDjUrlDisplay();
    updatePresenterUrlDisplay();
    loadSlidesDeck();
    loadPresentationDeck();
    pollSlideshowState();
    if (slideshowPollTimer) clearInterval(slideshowPollTimer);
    slideshowPollTimer = setInterval(pollSlideshowState, 1000);
}

function updateDjUrlDisplay() {
    const el = document.getElementById('dj-slideshow-url');
    if (el) {
        const host = getVenueHost();
        el.innerText = `http://${host}:8010/slideshow`;
    }
}

function copyDjSlideshowUrl() {
    const host = getVenueHost();
    const url = `http://${host}:8010/slideshow`;
    copyToClipboard(url);
}

function updatePresenterUrlDisplay() {
    const el = document.getElementById('presenter-remote-url');
    if (el) {
        const host = getVenueHost();
        el.innerText = `http://${host}:8010/presenter`;
    }
}

function copyPresenterUrl() {
    const host = getVenueHost();
    const url = `http://${host}:8010/presenter`;
    copyToClipboard(url);
}

function closeSlideshowModal() {
    const modal = document.getElementById('slideshow-modal');
    if (modal) modal.style.display = 'none';
}

async function pollSlideshowState() {
    try {
        const res = await fetch('/api/slideshow/state');
        const data = await res.json();
        if (data.status !== 'success' || !data.state) return;

        const state = data.state;
        const mode = state.mode || 'slideshow';
        const cd = state.countdown || {};

        const modeBadge = document.getElementById('ss-mode-badge');
        const timeBadge = document.getElementById('ss-time-badge');

        if (!modeBadge || !timeBadge) return;

        if (mode === 'bison_countdown' && cd.active) {
            modeBadge.innerText = '🏇 RACE COUNTDOWN ACTIVE';
            modeBadge.style.background = 'rgba(255, 71, 87, 0.2)';
            modeBadge.style.borderColor = '#ff4757';
            modeBadge.style.color = '#ff4757';

            const remaining = Math.max(0, Math.floor(cd.target_timestamp - (Date.now() / 1000)));
            const m = Math.floor(remaining / 60);
            const s = remaining % 60;
            timeBadge.innerText = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')} REMAINING`;
            timeBadge.style.color = remaining <= 30 ? '#ff4757' : '#ffd700';
            timeBadge.style.borderColor = remaining <= 30 ? '#ff4757' : '#ffd700';
        } else if (mode === 'presentation' || (state.presentation && state.presentation.active)) {
            const pres = state.presentation || {};
            const cur = (pres.current_index || 0) + 1;
            const tot = currentPresentationDeck ? currentPresentationDeck.length : 0;
            modeBadge.innerText = `📢 PRESENTATION ACTIVE (SLIDE ${cur}/${tot})`;
            modeBadge.style.background = 'rgba(255, 170, 0, 0.2)';
            modeBadge.style.borderColor = '#ffaa00';
            modeBadge.style.color = '#ffaa00';
            timeBadge.innerText = `SLIDE ${cur} OF ${tot}`;
            timeBadge.style.color = '#ffd700';
            timeBadge.style.borderColor = '#ffaa00';
        } else if (mode === 'bison_prerace') {
            modeBadge.innerText = '🏁 PRE-RACE SLIDE';
            modeBadge.style.background = 'rgba(155, 93, 229, 0.2)';
            modeBadge.style.borderColor = '#9b5de5';
            modeBadge.style.color = '#9b5de5';
            timeBadge.innerText = 'MANUAL OVERRIDE';
            timeBadge.style.color = '#8b949e';
            timeBadge.style.borderColor = 'var(--border)';
        } else if (mode === 'bison_race') {
            modeBadge.innerText = '🏇 LIVE RACE TRACK';
            modeBadge.style.background = 'rgba(0, 255, 204, 0.2)';
            modeBadge.style.borderColor = '#00ffcc';
            modeBadge.style.color = '#00ffcc';
            timeBadge.innerText = 'MANUAL OVERRIDE';
            timeBadge.style.color = '#8b949e';
            timeBadge.style.borderColor = 'var(--border)';
        } else {
            modeBadge.innerText = '📽️ SLIDESHOW ACTIVE';
            modeBadge.style.background = 'rgba(0, 255, 204, 0.12)';
            modeBadge.style.borderColor = 'var(--accent)';
            modeBadge.style.color = 'var(--accent)';
            timeBadge.innerText = 'NORMAL ROTATION';
            timeBadge.style.color = '#8b949e';
            timeBadge.style.borderColor = 'var(--border)';
        }

        // Presentation section indicators
        const presBadge = document.getElementById('pres-status-badge');
        const presIndicator = document.getElementById('pres-slide-indicator');
        const pres = state.presentation || {};
        const presActive = mode === 'presentation' || !!pres.active;
        const curIdx = pres.current_index || 0;
        const totalPres = currentPresentationDeck ? currentPresentationDeck.length : 0;

        if (presBadge) {
            if (presActive) {
                presBadge.innerText = 'LIVE ON PROJECTOR';
                presBadge.style.background = 'rgba(255, 170, 0, 0.2)';
                presBadge.style.borderColor = '#ffaa00';
                presBadge.style.color = '#ffaa00';
            } else {
                presBadge.innerText = 'INACTIVE';
                presBadge.style.background = 'rgba(255, 255, 255, 0.06)';
                presBadge.style.borderColor = 'var(--border)';
                presBadge.style.color = '#8b949e';
            }
        }
        if (presIndicator) {
            presIndicator.innerText = totalPres > 0 ? `Slide ${curIdx + 1} / ${totalPres}` : 'No slides';
        }
    } catch(e) {}
}

// --- Stage Presentation Management ---

async function loadPresentationDeck() {
    try {
        const res = await fetch('/api/slides/presentation');
        const data = await res.json();
        if (data.status === 'success') {
            currentPresentationDeck = data.slides || [];
            renderPresentationDeck(currentPresentationDeck);
        }
    } catch(e) {
        console.error('Error loading presentation slides:', e);
    }
}

function renderPresentationDeck(slides) {
    const container = document.getElementById('pres-slides-container');
    const countEl = document.getElementById('pres-slide-count');
    if (!container) return;

    container.innerHTML = '';
    if (countEl) countEl.innerText = `${slides.length} slides loaded`;

    if (slides.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 15px; font-size: 0.85rem;">No presentation slides yet. Select an image above to upload.</div>`;
        return;
    }

    slides.forEach((slide, idx) => {
        const card = document.createElement('div');
        card.style.cssText = `
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #111723;
            border: 1px solid rgba(255, 170, 0, 0.25);
            border-radius: 6px;
            padding: 8px 12px;
            gap: 10px;
        `;

        const leftBox = document.createElement('div');
        leftBox.style.cssText = 'display: flex; align-items: center; gap: 10px; flex: 1;';

        const orderBadge = document.createElement('span');
        orderBadge.style.cssText = 'font-family: monospace; font-size: 0.82rem; color: #ffd700; width: 24px; font-weight: bold;';
        orderBadge.innerText = `#${idx + 1}`;
        leftBox.appendChild(orderBadge);

        if (slide.url) {
            const thumb = document.createElement('img');
            thumb.src = slide.url;
            thumb.style.cssText = 'width: 52px; height: 29px; object-fit: cover; border-radius: 3px; border: 1px solid var(--border);';
            leftBox.appendChild(thumb);
        }

        const titleBox = document.createElement('div');
        titleBox.innerHTML = `
            <div style="font-size: 0.88rem; font-weight: bold; color: #fff; display: flex; align-items: center; gap: 6px;">
                ${slide.title || 'Presentation Slide ' + (idx + 1)}
                <span style="background: rgba(255, 170, 0, 0.15); border: 1px solid #ffaa00; color: #ffaa00; font-size: 0.68rem; padding: 2px 6px; border-radius: 3px; font-weight: bold;">1920x1080</span>
            </div>
            <div style="font-size: 0.72rem; color: var(--text-secondary); margin-top: 2px;">
                ID: <span style="font-family: monospace;">${slide.id}</span>
            </div>
        `;
        leftBox.appendChild(titleBox);
        card.appendChild(leftBox);

        const rightBox = document.createElement('div');
        rightBox.style.cssText = 'display: flex; align-items: center; gap: 6px;';

        const btnShow = document.createElement('button');
        btnShow.className = 'btn-mini';
        btnShow.style.cssText = 'background: rgba(255, 170, 0, 0.2); border: 1px solid #ffaa00; color: #ffaa00; font-weight: bold; padding: 4px 8px;';
        btnShow.innerText = '▶ Present';
        btnShow.title = 'Project this specific slide now';
        btnShow.onclick = () => startPresentation(idx);
        rightBox.appendChild(btnShow);

        const btnUp = document.createElement('button');
        btnUp.className = 'btn-mini';
        btnUp.style.cssText = 'background: #21262d; color: #fff; padding: 4px 8px;';
        btnUp.innerText = '▲';
        btnUp.disabled = idx === 0;
        btnUp.onclick = () => movePresentationSlide(slide.id, -1);
        rightBox.appendChild(btnUp);

        const btnDown = document.createElement('button');
        btnDown.className = 'btn-mini';
        btnDown.style.cssText = 'background: #21262d; color: #fff; padding: 4px 8px;';
        btnDown.innerText = '▼';
        btnDown.disabled = idx === slides.length - 1;
        btnDown.onclick = () => movePresentationSlide(slide.id, 1);
        rightBox.appendChild(btnDown);

        const btnDel = document.createElement('button');
        btnDel.className = 'btn-mini btn-stop';
        btnDel.style.cssText = 'padding: 4px 8px;';
        btnDel.innerText = '🗑️';
        btnDel.title = 'Delete presentation slide';
        btnDel.onclick = () => deletePresentationSlide(slide.id);
        rightBox.appendChild(btnDel);

        card.appendChild(rightBox);
        container.appendChild(card);
    });
}

async function uploadPresentationSlide() {
    const fileInput = document.getElementById('pres-upload-file');
    const titleInput = document.getElementById('pres-upload-title');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast('Please select an image file to upload.', 'error');
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('deck', 'presentation');
    if (titleInput && titleInput.value.trim()) {
        formData.append('title', titleInput.value.trim());
    }

    showToast('Uploading presentation slide (resizing to 1920x1080)...', 'success');

    try {
        const res = await fetch('/api/slides/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('✓ Presentation slide uploaded & resized to 1920x1080!', 'success');
            fileInput.value = '';
            if (titleInput) titleInput.value = '';
            loadPresentationDeck();
        } else {
            showToast('Upload failed: ' + (data.message || 'Unknown'), 'error');
        }
    } catch(e) {
        showToast(`Upload error: ${e.message}`, 'error');
    }
}

async function deletePresentationSlide(slideId) {
    if (!confirm('Are you sure you want to delete this presentation slide?')) return;
    try {
        const res = await fetch(`/api/slides/presentation/${slideId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('Presentation slide deleted.', 'success');
            loadPresentationDeck();
        } else {
            showToast('Failed to delete presentation slide', 'error');
        }
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function movePresentationSlide(slideId, delta) {
    const ids = currentPresentationDeck.map(s => s.id);
    const currIdx = ids.indexOf(slideId);
    if (currIdx === -1) return;

    const targetIdx = currIdx + delta;
    if (targetIdx < 0 || targetIdx >= ids.length) return;

    const temp = ids[currIdx];
    ids[currIdx] = ids[targetIdx];
    ids[targetIdx] = temp;

    try {
        const res = await fetch('/api/slides/presentation/reorder', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ slide_ids: ids })
        });
        const data = await res.json();
        if (data.status === 'success') {
            loadPresentationDeck();
        }
    } catch(e) {
        showToast(`Error reordering presentation: ${e.message}`, 'error');
    }
}

async function startPresentation(slideIndex = 0) {
    try {
        const res = await fetch('/api/slideshow/presentation/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ slide_index: slideIndex })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`📢 Presentation Live on Projector (Slide #${slideIndex + 1})!`, 'success');
            pollSlideshowState();
        }
    } catch(e) {
        showToast(`Error starting presentation: ${e.message}`, 'error');
    }
}

async function stopPresentation() {
    try {
        const res = await fetch('/api/slideshow/presentation/stop', {
            method: 'POST'
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('⏹️ Presentation stopped. Returned to regular slideshow.', 'success');
            pollSlideshowState();
        }
    } catch(e) {
        showToast(`Error stopping presentation: ${e.message}`, 'error');
    }
}

async function stepPresentation(delta) {
    try {
        const res = await fetch('/api/slideshow/presentation/step', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ delta: delta })
        });
        const data = await res.json();
        if (data.status === 'success') {
            pollSlideshowState();
        }
    } catch(e) {
        showToast(`Error stepping presentation: ${e.message}`, 'error');
    }
}

async function restartRegularSlideshow() {
    try {
        const res = await fetch('/api/slideshow/restart_regular', {
            method: 'POST'
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('✓ Regular slideshow restarted from Slide 1!', 'success');
            pollSlideshowState();
        } else {
            showToast('Failed to restart slideshow', 'error');
        }
    } catch(e) {
        showToast(`Error restarting slideshow: ${e.message}`, 'error');
    }
}

function setCountdownPreset(min) {
    const minInput = document.getElementById('bison-cd-min');
    const secInput = document.getElementById('bison-cd-sec');
    if (minInput) minInput.value = min;
    if (secInput) secInput.value = 0;
}

async function startBisonCountdown() {
    const min = parseFloat(document.getElementById('bison-cd-min').value) || 0;
    const sec = parseInt(document.getElementById('bison-cd-sec').value) || 0;
    const title = document.getElementById('bison-cd-title').value.trim() || 'Next Bison Dash Race';

    if (min === 0 && sec < 5) {
        showToast('Please specify at least 5 seconds for the countdown.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/slideshow/bison/start_countdown', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ minutes: min, seconds: sec, title: title })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`🚀 Started Race Countdown (${min}m ${sec}s)!`, 'success');
            pollSlideshowState();
        } else {
            showToast('Failed to start race countdown: ' + (data.message || 'Unknown'), 'error');
        }
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function stopBisonCountdown() {
    try {
        const res = await fetch('/api/slideshow/bison/stop', {
            method: 'POST'
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('⏹️ Race mode stopped. Returned to Slideshow.', 'success');
            pollSlideshowState();
        } else {
            showToast('Failed to stop race mode', 'error');
        }
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function setBisonMode(mode) {
    try {
        const res = await fetch('/api/slideshow/bison/set_mode', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ mode: mode })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`Screen mode set to: ${mode}`, 'success');
            pollSlideshowState();
        }
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function loadSlidesDeck() {
    try {
        const res = await fetch('/api/slides');
        const data = await res.json();
        if (data.status === 'success') {
            currentSlidesDeck = data.slides || [];
            renderSlidesDeck(currentSlidesDeck);
        }
    } catch(e) {
        showToast(`Error loading slides: ${e.message}`, 'error');
    }
}

function renderSlidesDeck(slides) {
    const container = document.getElementById('ss-slides-container');
    const countEl = document.getElementById('ss-slide-count');
    if (!container) return;

    container.innerHTML = '';
    const activeCount = slides.filter(s => s.enabled).length;
    if (countEl) countEl.innerText = `${slides.length} slides loaded (${activeCount} enabled)`;

    if (slides.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--text-secondary); padding: 15px;">No slides found.</div>`;
        return;
    }

    slides.forEach((slide, idx) => {
        const card = document.createElement('div');
        card.style.cssText = `
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #111723;
            border: 1px solid ${slide.enabled ? 'var(--border)' : 'rgba(255,255,255,0.05)'};
            border-radius: 6px;
            padding: 8px 12px;
            opacity: ${slide.enabled ? '1' : '0.5'};
            transition: all 0.15s;
        `;

        // Left info
        const leftBox = document.createElement('div');
        leftBox.style.cssText = 'display: flex; align-items: center; gap: 10px; flex: 1;';

        // Order badge
        const orderBadge = document.createElement('span');
        orderBadge.style.cssText = 'font-family: monospace; font-size: 0.8rem; color: var(--text-secondary); width: 22px;';
        orderBadge.innerText = `#${idx + 1}`;
        leftBox.appendChild(orderBadge);

        // Thumbnail / Icon
        if (slide.type === 'custom_image' && slide.url) {
            const thumb = document.createElement('img');
            thumb.src = slide.url;
            thumb.style.cssText = 'width: 48px; height: 27px; object-fit: cover; border-radius: 3px; border: 1px solid var(--border);';
            leftBox.appendChild(thumb);
        } else if (slide.type === 'leaderboard') {
            const icon = document.createElement('div');
            icon.innerText = '🏆';
            icon.style.cssText = 'font-size: 1.2rem; width: 48px; text-align: center;';
            leftBox.appendChild(icon);
        } else {
            const icon = document.createElement('div');
            icon.innerText = '📄';
            icon.style.cssText = 'font-size: 1.2rem; width: 48px; text-align: center;';
            leftBox.appendChild(icon);
        }

        // Title and Type tag
        const titleBox = document.createElement('div');
        let typeBadge = '';
        if (slide.type === 'leaderboard') {
            typeBadge = `<span style="background: rgba(255, 215, 0, 0.15); border: 1px solid #ffd700; color: #ffd700; font-size: 0.7rem; padding: 2px 6px; border-radius: 3px; margin-left: 6px; font-weight: bold;">LIVE LEADERBOARD (IN MIX)</span>`;
        } else if (slide.type === 'custom_image') {
            typeBadge = `<span style="background: rgba(0, 255, 204, 0.12); border: 1px solid var(--accent); color: var(--accent); font-size: 0.7rem; padding: 2px 6px; border-radius: 3px; margin-left: 6px; font-weight: bold;">1920x1080 RESIZED</span>`;
        } else {
            typeBadge = `<span style="background: rgba(255, 255, 255, 0.08); border: 1px solid var(--border); color: var(--text-secondary); font-size: 0.7rem; padding: 2px 6px; border-radius: 3px; margin-left: 6px;">BUILT-IN</span>`;
        }

        titleBox.innerHTML = `
            <div style="font-size: 0.88rem; font-weight: bold; color: #fff; display: flex; align-items: center; flex-wrap: wrap;">
                ${slide.title || 'Slide ' + (idx + 1)} ${typeBadge}
            </div>
            <div style="font-size: 0.74rem; color: var(--text-secondary); margin-top: 2px;">
                Duration: ${slide.duration || 10}s &bull; ID: <span style="font-family: monospace;">${slide.id}</span>
            </div>
        `;
        leftBox.appendChild(titleBox);
        card.appendChild(leftBox);

        // Actions
        const rightBox = document.createElement('div');
        rightBox.style.cssText = 'display: flex; align-items: center; gap: 8px;';

        // Enabled toggle
        const toggleLabel = document.createElement('label');
        toggleLabel.style.cssText = 'display: flex; align-items: center; gap: 4px; font-size: 0.78rem; cursor: pointer; color: var(--text-secondary); margin-right: 6px;';
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.checked = !!slide.enabled;
        chk.onchange = () => toggleSlide(slide.id, chk.checked);
        toggleLabel.appendChild(chk);
        toggleLabel.appendChild(document.createTextNode('Enabled'));
        rightBox.appendChild(toggleLabel);

        // Move Up / Down
        const btnUp = document.createElement('button');
        btnUp.className = 'btn-mini';
        btnUp.style.cssText = 'background: #21262d; color: #fff; padding: 4px 8px;';
        btnUp.innerText = '▲';
        btnUp.disabled = idx === 0;
        btnUp.onclick = () => moveSlide(slide.id, -1);
        rightBox.appendChild(btnUp);

        const btnDown = document.createElement('button');
        btnDown.className = 'btn-mini';
        btnDown.style.cssText = 'background: #21262d; color: #fff; padding: 4px 8px;';
        btnDown.innerText = '▼';
        btnDown.disabled = idx === slides.length - 1;
        btnDown.onclick = () => moveSlide(slide.id, 1);
        rightBox.appendChild(btnDown);

        // Delete (for custom images)
        if (slide.type === 'custom_image') {
            const btnDel = document.createElement('button');
            btnDel.className = 'btn-mini btn-stop';
            btnDel.style.cssText = 'padding: 4px 8px;';
            btnDel.innerText = '🗑️';
            btnDel.title = 'Delete slide';
            btnDel.onclick = () => deleteSlide(slide.id);
            rightBox.appendChild(btnDel);
        }

        card.appendChild(rightBox);
        container.appendChild(card);
    });
}

async function uploadCustomSlide() {
    const fileInput = document.getElementById('ss-upload-file');
    const titleInput = document.getElementById('ss-upload-title');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast('Please select an image file to upload.', 'error');
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    if (titleInput && titleInput.value.trim()) {
        formData.append('title', titleInput.value.trim());
    }

    showToast('Uploading and resizing to 1920x1080...', 'success');

    try {
        const res = await fetch('/api/slides/upload', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('✓ Slide uploaded & resized to 1920x1080!', 'success');
            fileInput.value = '';
            if (titleInput) titleInput.value = '';
            loadSlidesDeck();
        } else {
            showToast('Upload failed: ' + (data.message || 'Unknown'), 'error');
        }
    } catch(e) {
        showToast(`Upload error: ${e.message}`, 'error');
    }
}

async function toggleSlide(slideId, isEnabled) {
    try {
        const res = await fetch('/api/slides/toggle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ slide_id: slideId, enabled: isEnabled })
        });
        const data = await res.json();
        if (data.status === 'success') {
            loadSlidesDeck();
        } else {
            showToast('Failed to toggle slide', 'error');
        }
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function deleteSlide(slideId) {
    if (!confirm('Are you sure you want to delete this custom slide?')) return;
    try {
        const res = await fetch(`/api/slides/${slideId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('Slide removed from playlist.', 'success');
            loadSlidesDeck();
        } else {
            showToast('Failed to delete slide', 'error');
        }
    } catch(e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function moveSlide(slideId, delta) {
    const ids = currentSlidesDeck.map(s => s.id);
    const currIdx = ids.indexOf(slideId);
    if (currIdx === -1) return;

    const targetIdx = currIdx + delta;
    if (targetIdx < 0 || targetIdx >= ids.length) return;

    // Swap
    const temp = ids[currIdx];
    ids[currIdx] = ids[targetIdx];
    ids[targetIdx] = temp;

    try {
        const res = await fetch('/api/slides/reorder', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ slide_ids: ids })
        });
        const data = await res.json();
        if (data.status === 'success') {
            loadSlidesDeck();
        }
    } catch(e) {
        showToast(`Error reordering: ${e.message}`, 'error');
    }
}

// Initial polling
setInterval(pollProcessStatus, 5000);
pollProcessStatus();

// --- QUICK LOOK INITIALIZATION ---

function switchTab(tabName) {
    const tabs = ['bisondash', 'slideshow', 'manifest', 'qr', 'economy'];
    tabs.forEach(t => {
        const btn = document.getElementById(`tab-btn-${t}`);
        const pane = document.getElementById(`pane-${t}`);
        if (btn) {
            if (t === tabName) btn.classList.add('active');
            else btn.classList.remove('active');
        }
        if (pane) {
            if (t === tabName) pane.classList.add('active');
            else pane.classList.remove('active');
        }
    });
}

// Hook Bison Dash state to Header Status Pill
function syncHeaderBisonPill() {
    const bdStateEl = document.getElementById('bd-current-state');
    const headerStatus = document.getElementById('header-bison-status');
    const headerPill = document.getElementById('header-bison-pill');

    if (bdStateEl && headerStatus) {
        const text = bdStateEl.innerText.trim();
        if (text && text !== 'Unknown' && text !== 'Connecting...') {
            headerStatus.innerText = text.replace(/_/g, ' ');
            if (headerPill) {
                if (text === 'Betting_Open') {
                    headerPill.className = 'status-pill active-state';
                } else if (text === 'Disconnected') {
                    headerPill.className = 'status-pill';
                } else {
                    headerPill.className = 'status-pill online';
                }
            }
        }
    }
}

// Initialize on load
function initVenueCommand() {
    loadAdminManifest();
    pollSlideshowState();

    if (slideshowPollTimer) clearInterval(slideshowPollTimer);
    slideshowPollTimer = setInterval(pollSlideshowState, 1500);

    // Sync header status pill
    setInterval(syncHeaderBisonPill, 1000);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initVenueCommand);
} else {
    initVenueCommand();
}


