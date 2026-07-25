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
