function showToast(message, type = 'error') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerText = message;
    document.body.appendChild(toast);

    // Animate in
    setTimeout(() => { toast.classList.add('show'); }, 10);

    // Remove after 5s
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

async function fetchStatus() {
    try {
        const res = await fetch('/api/process/status');
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();
        renderGrid(data);
    } catch (e) {
        showToast(`Failed to fetch status: ${e.message}`, 'error');
    }
}

function renderGrid(statusData) {
    const grid = document.getElementById('games-grid');
    grid.innerHTML = '';

    for (const [gameId, info] of Object.entries(statusData)) {
        const isRunning = info.running;
        const statusClass = isRunning ? 'status-running' : 'status-stopped';
        const statusText = isRunning ? `ON (Port ${info.port})` : 'OFF';

        const card = document.createElement('div');
        card.className = 'game-card';
        card.innerHTML = `
            <div class="game-header">
                <div class="game-title">${gameId.replace('_', ' ').toUpperCase()}</div>
                <div class="status-badge ${statusClass}">${statusText}</div>
            </div>
            <div class="controls">
                <button class="action-btn start" onclick="startProcess('${gameId}')">START</button>
                <button class="action-btn stop" onclick="stopProcess('${gameId}')">STOP</button>
            </div>
        `;
        grid.appendChild(card);
    }
}

async function startProcess(gameId) {
    try {
        const res = await fetch('/api/process/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId})
        });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        fetchStatus();
    } catch(e) {
        showToast(`Error starting process ${gameId}: ${e.message}`, 'error');
    }
}

async function stopProcess(gameId) {
    try {
        const res = await fetch('/api/process/stop', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: gameId})
        });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        fetchStatus();
    } catch(e) {
        showToast(`Error stopping process ${gameId}: ${e.message}`, 'error');
    }
}

async function globalReset() {
    if(confirm("DANGER: This will broadcast a reset to all active game ports. Are you sure?")) {
        try {
            const res = await fetch('/api/global/reset', { method: 'POST' });
            if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
            showToast("Global reset payload broadcasted.", 'success');
        } catch(e) {
            showToast(`Error sending global reset: ${e.message}`, 'error');
        }
    }
}

async function fetchLogs() {
    try {
        const res = await fetch('/api/global/logs');
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();
        const container = document.getElementById('logs-container');
        container.innerHTML = data.logs.map(l => `<div class="log-line">${l}</div>`).join('');
        container.scrollTop = container.scrollHeight;
    } catch(e) {
        showToast(`Error fetching logs: ${e.message}`, 'error');
    }
}

async function injectTokens() {
    const pid = document.getElementById('player-id').value;
    const amt = parseInt(document.getElementById('token-amount').value);
    if(!pid || isNaN(amt)) return alert("Invalid inputs");

    try {
        const res = await fetch('/api/admin/inject-tokens', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({player_id: pid, amount: amt})
        });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();
        showToast(`Tokens injected. New balance for ${pid}: ${data.new_balance}`, 'success');
    } catch(e) {
        showToast(`Error injecting tokens: ${e.message}`, 'error');
    }
}

async function loadSettings() {
    try {
        const res = await fetch('/api/admin/settings');
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();
        if (data.status === 'success') {
            document.getElementById('tailscale-enforcement-cb').checked = data.settings.tailscale_enforcement;
            document.getElementById('tailscale-ip-pool').value = data.settings.tailscale_ip_pool;
        }
    } catch(e) {
        showToast(`Error loading settings: ${e.message}`, 'error');
    }
}

async function updateSettings() {
    const enforcement = document.getElementById('tailscale-enforcement-cb').checked;
    const pool = document.getElementById('tailscale-ip-pool').value;

    try {
        const res = await fetch('/api/admin/settings/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                tailscale_enforcement: enforcement,
                tailscale_ip_pool: pool
            })
        });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();
        if (data.status === 'success') {
            showToast("Settings saved successfully.", 'success');
        }
    } catch(e) {
        showToast(`Error updating settings: ${e.message}`, 'error');
    }
}

// Loops
setInterval(fetchStatus, 2000);
setInterval(fetchLogs, 1000);
fetchStatus();
fetchLogs();
loadSettings();
