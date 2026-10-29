/**
 * pin_auth_flow.js
 * Standardized 3-Step PIN Authentication & Identity Confirmation across all event interfaces.
 * 
 * Flow:
 * - Step 1: 4-Digit PIN Input (<input type="tel" maxlength="4" pattern="[0-9]*">) + Numeric Keypad.
 *   On 4 digits entered, automatically calls POST /api/attendee/lookup.
 * - Step 2: Confirmation Screen displaying Display Name, Email, Token Balance.
 *   Exactly two action buttons with verbatim labels: "Confirm" and "Cancel".
 *   Clicking "Cancel": Clears input and immediately resets to Step 1.
 *   Clicking "Confirm": Advances to Step 3.
 * - Step 3: Station Action & Auto-Reset on completion back to Step 1.
 * - NO sessionStorage or localStorage persistence. Clean state every cycle.
 */

(function (window) {
    'use strict';

    let instanceCounter = 0;

    class PinAuthFlow {
        /**
         * @param {Object} options
         * @param {string} options.containerId - Element ID where the PIN keypad renders
         * @param {boolean} [options.isModal=false] - Whether Step 1 itself is a popup modal
         * @param {string} [options.title] - Station check-in title
         * @param {string} [options.subtitle] - Station check-in subtitle
         * @param {Function} options.onConfirmed - Callback fn(attendee) when user clicks "Confirm" in Step 2
         * @param {Function} [options.onCancel] - Optional callback when user clicks "Cancel" in Step 2
         * @param {string} [options.apiHost] - Base API host (defaults to current origin)
         */
        constructor(options = {}) {
            this.instanceId = ++instanceCounter;
            this.containerId = options.containerId || `pin-auth-container-${this.instanceId}`;
            this.isModal = !!options.isModal;
            this.title = options.title || 'ENTER 4-DIGIT PIN';
            this.subtitle = options.subtitle || 'Enter your assigned attendee PIN on the keypad below';
            this.tokenCost = options.tokenCost !== undefined ? Number(options.tokenCost) : (options.cost !== undefined ? Number(options.cost) : null);
            this.onInsufficientTokens = options.onInsufficientTokens || null;
            this.onConfirmed = options.onConfirmed || function () {};
            this.onCancel = options.onCancel || function () {};
            this.apiHost = options.apiHost || '';
            
            this.currentPin = '';
            this.activeAttendee = null;
            this.isVerifying = false;

            this.injectStyles();
            this.render();
            this.bindEvents();
        }

        injectStyles() {
            if (document.getElementById('pin-auth-flow-styles')) return;
            const style = document.createElement('style');
            style.id = 'pin-auth-flow-styles';
            style.textContent = `
                /* PIN AUTH FLOW STANDARDIZED STYLING */
                .paf-wrapper {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    width: 100%;
                    max-width: 440px;
                    margin: 0 auto;
                    user-select: none;
                    -webkit-user-select: none;
                }
                .paf-header {
                    text-align: center;
                    margin-bottom: 16px;
                }
                .paf-title {
                    font-size: 1.5rem;
                    font-weight: 800;
                    letter-spacing: 1px;
                    color: var(--accent, #00ffcc);
                    text-transform: uppercase;
                    margin-bottom: 4px;
                }
                .paf-subtitle {
                    font-size: 0.85rem;
                    color: var(--text-muted, #8b949e);
                }
                .paf-cost-pill {
                    background: rgba(255, 215, 0, 0.15);
                    border: 1px solid var(--gold, #ffd700);
                    color: var(--gold, #ffd700);
                    font-size: 0.86rem;
                    font-weight: 800;
                    letter-spacing: 0.8px;
                    padding: 5px 14px;
                    border-radius: 20px;
                    margin-top: 6px;
                    text-transform: uppercase;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    box-shadow: 0 0 12px rgba(255, 215, 0, 0.2);
                }
                .paf-pad-card {
                    background: rgba(17, 23, 34, 0.95);
                    border: 2px solid var(--border, #222d3d);
                    border-radius: 16px;
                    padding: 24px 20px 20px 20px;
                    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
                    width: 100%;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    position: relative;
                }
                .paf-input-wrapper {
                    position: relative;
                    width: 100%;
                    display: flex;
                    justify-content: center;
                    margin-bottom: 12px;
                }
                .paf-hidden-input {
                    position: absolute;
                    opacity: 0;
                    width: 100%;
                    height: 100%;
                    top: 0;
                    left: 0;
                    z-index: 5;
                    pointer-events: none;
                    border: none;
                    background: transparent;
                    color: transparent;
                }
                .paf-boxes {
                    display: flex;
                    gap: 14px;
                    justify-content: center;
                    pointer-events: none;
                }
                .paf-digit-box {
                    width: 54px;
                    height: 64px;
                    background: #090d16;
                    border: 2px solid var(--border, #30363d);
                    border-radius: 12px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 2rem;
                    font-family: Consolas, monospace, sans-serif;
                    font-weight: 900;
                    color: #fff;
                    transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                }
                .paf-digit-box.filled {
                    border-color: var(--accent, #00ffcc);
                    color: var(--accent, #00ffcc);
                    box-shadow: 0 0 16px rgba(0, 255, 204, 0.35);
                    transform: scale(1.04);
                }
                .paf-digit-box.active {
                    border-color: #ffd700;
                    box-shadow: 0 0 16px rgba(255, 215, 0, 0.4);
                    animation: pafPulse 1s infinite alternate;
                }
                @keyframes pafPulse {
                    from { transform: scale(1); }
                    to { transform: scale(1.06); }
                }
                .paf-status-msg {
                    font-size: 0.88rem;
                    min-height: 24px;
                    margin-bottom: 14px;
                    text-align: center;
                    font-weight: 700;
                    color: var(--text-muted, #8b949e);
                    transition: color 0.2s ease;
                }
                .paf-status-msg.error {
                    color: #ff4757;
                }
                .paf-status-msg.success {
                    color: #2ed573;
                }
                .paf-grid {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 10px;
                    width: 100%;
                    max-width: 320px;
                }
                .paf-key-btn {
                    height: 58px;
                    background: #161b22;
                    border: 1px solid var(--border, #30363d);
                    border-radius: 10px;
                    color: #f0f6fc;
                    font-size: 1.5rem;
                    font-weight: 800;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: all 0.1s ease;
                    touch-action: manipulation;
                }
                .paf-key-btn:active {
                    background: var(--accent, #00ffcc);
                    color: #000;
                    transform: scale(0.96);
                }
                .paf-key-btn.btn-action {
                    background: #21262d;
                    color: #8b949e;
                    font-size: 1.05rem;
                    font-weight: 700;
                }
                .paf-key-btn.btn-action:active {
                    background: #30363d;
                    color: #fff;
                }

                /* MODAL OVERLAY FOR MODAL MODE */
                .paf-step1-modal-overlay {
                    position: fixed;
                    inset: 0;
                    width: 100vw;
                    height: 100vh;
                    background: rgba(4, 7, 13, 0.92);
                    backdrop-filter: blur(8px);
                    display: none;
                    align-items: center;
                    justify-content: center;
                    z-index: 99998;
                    padding: 16px;
                }

                /* STEP 2: MANDATORY CONFIRMATION MODAL */
                .paf-modal-overlay {
                    position: fixed;
                    inset: 0;
                    width: 100vw;
                    height: 100vh;
                    background: rgba(4, 7, 13, 0.94);
                    backdrop-filter: blur(8px);
                    display: none;
                    align-items: center;
                    justify-content: center;
                    z-index: 99999;
                    padding: 16px;
                }
                .paf-modal-box {
                    background: #111722;
                    border: 2px solid var(--accent, #00ffcc);
                    border-radius: 20px;
                    padding: 28px 24px 22px 24px;
                    max-width: 440px;
                    width: 100%;
                    text-align: center;
                    box-shadow: 0 15px 50px rgba(0, 0, 0, 0.9), 0 0 35px rgba(0, 255, 204, 0.25);
                    animation: pafModalPop 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                }
                @keyframes pafModalPop {
                    from { transform: scale(0.85); opacity: 0; }
                    to { transform: scale(1); opacity: 1; }
                }
                .paf-modal-tag {
                    display: inline-block;
                    font-size: 0.75rem;
                    font-weight: 800;
                    letter-spacing: 1.5px;
                    color: var(--accent, #00ffcc);
                    text-transform: uppercase;
                    background: rgba(0, 255, 204, 0.12);
                    border: 1px solid var(--accent, #00ffcc);
                    padding: 4px 12px;
                    border-radius: 20px;
                    margin-bottom: 12px;
                }
                .paf-modal-heading {
                    font-size: 1.4rem;
                    font-weight: 900;
                    color: #fff;
                    margin-bottom: 16px;
                }
                .paf-confirm-card {
                    background: #090d16;
                    border: 1px solid var(--border, #222d3d);
                    border-radius: 12px;
                    padding: 18px 16px;
                    margin-bottom: 22px;
                    text-align: left;
                }
                .paf-detail-row {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 0;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
                }
                .paf-detail-row:last-child {
                    border-bottom: none;
                    padding-bottom: 0;
                }
                .paf-detail-label {
                    font-size: 0.78rem;
                    font-weight: 700;
                    color: var(--text-muted, #8b949e);
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .paf-detail-val {
                    font-size: 0.98rem;
                    font-weight: 800;
                    color: #fff;
                    text-align: right;
                    word-break: break-all;
                }
                .paf-balance-badge {
                    color: #ffd700;
                    font-size: 1.25rem;
                    font-family: Consolas, monospace;
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                }
                .paf-modal-actions {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 12px;
                }
                .paf-btn {
                    padding: 14px 18px;
                    border-radius: 10px;
                    font-size: 1.05rem;
                    font-weight: 900;
                    letter-spacing: 0.5px;
                    cursor: pointer;
                    transition: all 0.15s ease;
                    border: none;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    touch-action: manipulation;
                }
                .paf-btn:active {
                    transform: scale(0.97);
                }
                .paf-btn-cancel {
                    background: #21262d;
                    border: 1px solid #30363d;
                    color: #f0f6fc;
                }
                .paf-btn-cancel:hover {
                    background: #30363d;
                    color: #ff4757;
                }
                .paf-btn-confirm {
                    background: var(--accent, #00ffcc);
                    color: #000;
                    box-shadow: 0 0 20px rgba(0, 255, 204, 0.4);
                }
                .paf-btn-confirm:hover {
                    filter: brightness(1.1);
                }
            `;
            document.head.appendChild(style);
        }

        render() {
            let container = document.getElementById(this.containerId);
            if (!container && this.isModal) {
                container = document.createElement('div');
                container.id = this.containerId;
                document.body.appendChild(container);
            }
            if (!container) return;

            const modalCloseBtn = '';

            const contentHtml = `
                <div class="paf-wrapper" id="paf-step-1-${this.instanceId}">
                    <div class="paf-header">
                        <div class="paf-title">${this.title}</div>
                        <div class="paf-subtitle">${this.subtitle}</div>
                        <div id="paf-cost-pill-${this.instanceId}" class="paf-cost-pill" style="${this.tokenCost && this.tokenCost > 0 ? '' : 'display:none;'}">🪙 ${this.tokenCost || 0} TOKENS TO PLAY</div>
                    </div>
                    <div class="paf-pad-card">
                        ${modalCloseBtn}
                        <div class="paf-input-wrapper">
                            <input type="tel" maxlength="4" pattern="[0-9]*" inputmode="none" readonly class="paf-hidden-input" id="paf-input-${this.instanceId}" autocomplete="off" />
                            <div class="paf-boxes" id="paf-boxes-${this.instanceId}">
                                <div class="paf-digit-box active" id="paf-box-0-${this.instanceId}">&bull;</div>
                                <div class="paf-digit-box" id="paf-box-1-${this.instanceId}">&bull;</div>
                                <div class="paf-digit-box" id="paf-box-2-${this.instanceId}">&bull;</div>
                                <div class="paf-digit-box" id="paf-box-3-${this.instanceId}">&bull;</div>
                            </div>
                        </div>
                        <div class="paf-status-msg" id="paf-status-${this.instanceId}">Tap digits or use keyboard</div>
                        <div class="paf-grid">
                            <button type="button" class="paf-key-btn" data-key="1">1</button>
                            <button type="button" class="paf-key-btn" data-key="2">2</button>
                            <button type="button" class="paf-key-btn" data-key="3">3</button>
                            <button type="button" class="paf-key-btn" data-key="4">4</button>
                            <button type="button" class="paf-key-btn" data-key="5">5</button>
                            <button type="button" class="paf-key-btn" data-key="6">6</button>
                            <button type="button" class="paf-key-btn" data-key="7">7</button>
                            <button type="button" class="paf-key-btn" data-key="8">8</button>
                            <button type="button" class="paf-key-btn" data-key="9">9</button>
                            <button type="button" class="paf-key-btn btn-action" id="paf-key-clear-${this.instanceId}">CLR</button>
                            <button type="button" class="paf-key-btn" data-key="0">0</button>
                            <button type="button" class="paf-key-btn btn-action" id="paf-key-backspace-${this.instanceId}">&#9003;</button>
                        </div>
                    </div>
                </div>
            `;

            if (this.isModal) {
                container.className = 'paf-step1-modal-overlay';
                container.innerHTML = `<div style="max-width: 440px; width: 100%; position: relative;">${contentHtml}</div>`;
            } else {
                container.innerHTML = contentHtml;
            }

            // Render Step 2 Confirmation Modal (in document body)
            let modal = document.getElementById(`paf-confirm-modal-${this.instanceId}`);
            if (!modal) {
                modal = document.createElement('div');
                modal.id = `paf-confirm-modal-${this.instanceId}`;
                modal.className = 'paf-modal-overlay';
                modal.innerHTML = `
                    <div class="paf-modal-box">
                        <div class="paf-modal-tag">Identity Verification</div>
                        <div class="paf-modal-heading">Confirm Attendee</div>
                        <div class="paf-confirm-card">
                            <div class="paf-detail-row">
                                <span class="paf-detail-label">Display Name</span>
                                <span class="paf-detail-val" id="paf-confirm-name-${this.instanceId}">Attendee</span>
                            </div>
                            <div class="paf-detail-row">
                                <span class="paf-detail-label">Email</span>
                                <span class="paf-detail-val" id="paf-confirm-email-${this.instanceId}">email@example.com</span>
                            </div>
                            <div class="paf-detail-row">
                                <span class="paf-detail-label">Current Balance</span>
                                <span class="paf-detail-val paf-balance-badge">
                                    <span>🪙</span> <span id="paf-confirm-balance-${this.instanceId}">0</span>
                                </span>
                            </div>
                            <div class="paf-detail-row" id="paf-row-cost-${this.instanceId}" style="display: none;">
                                <span class="paf-detail-label">Entry Fee</span>
                                <span class="paf-detail-val" style="color: var(--gold, #ffd700); font-weight: 800;" id="paf-confirm-cost-${this.instanceId}">-4 Tokens</span>
                            </div>
                            <div class="paf-detail-row" id="paf-row-after-${this.instanceId}" style="display: none;">
                                <span class="paf-detail-label">Balance After Play</span>
                                <span class="paf-detail-val" style="color: var(--accent, #00ffcc); font-weight: 800;" id="paf-confirm-after-${this.instanceId}">96 Tokens</span>
                            </div>
                        </div>
                        <div class="paf-modal-actions">
                            <button type="button" class="paf-btn paf-btn-cancel" id="paf-btn-cancel-${this.instanceId}">Cancel</button>
                            <button type="button" class="paf-btn paf-btn-confirm" id="paf-btn-confirm-${this.instanceId}">Confirm</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            }
        }

        bindEvents() {
            const container = document.getElementById(this.containerId);
            if (!container) return;

            // Keypad button taps
            container.querySelectorAll('.paf-key-btn[data-key]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.pressKey(btn.getAttribute('data-key'));
                });
            });

            const clearBtn = container.querySelector(`#paf-key-clear-${this.instanceId}`);
            if (clearBtn) {
                clearBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.clear();
                });
            }

            const backBtn = container.querySelector(`#paf-key-backspace-${this.instanceId}`);
            if (backBtn) {
                backBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.backspace();
                });
            }

            const modalCloseBtn = container.querySelector('.paf-close-modal-btn');
            if (modalCloseBtn) {
                modalCloseBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.close();
                });
            }

            // Hidden input binding
            const hiddenInput = container.querySelector(`#paf-input-${this.instanceId}`);
            if (hiddenInput) {
                hiddenInput.addEventListener('input', () => {
                    const clean = hiddenInput.value.replace(/\D/g, '').slice(0, 4);
                    this.currentPin = clean;
                    hiddenInput.value = clean;
                    this.updateDisplay();
                    if (this.currentPin.length === 4) {
                        this.lookupPin(this.currentPin);
                    }
                });
            }

            // Global keyboard listener
            window.addEventListener('keydown', (e) => {
                const step2Modal = document.getElementById(`paf-confirm-modal-${this.instanceId}`);
                if (step2Modal && step2Modal.style.display === 'flex') return;

                const step1Container = document.getElementById(this.containerId);
                if (!step1Container) return;
                if (this.isModal && step1Container.style.display !== 'flex') return;

                if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') && e.target.id !== `paf-input-${this.instanceId}`) {
                    return;
                }

                if (/^[0-9]$/.test(e.key)) {
                    this.pressKey(e.key);
                } else if (e.key === 'Backspace') {
                    this.backspace();
                } else if (e.key === 'Escape') {
                    this.clear();
                }
            });

            // Step 2 Modal Buttons
            const cancelBtn = document.getElementById(`paf-btn-cancel-${this.instanceId}`);
            if (cancelBtn) {
                cancelBtn.onclick = (e) => {
                    e.preventDefault();
                    this.onCancelClick();
                };
            }

            const confirmBtn = document.getElementById(`paf-btn-confirm-${this.instanceId}`);
            if (confirmBtn) {
                confirmBtn.onclick = (e) => {
                    e.preventDefault();
                    this.onConfirmClick();
                };
            }
        }

        open() {
            const container = document.getElementById(this.containerId);
            if (container) {
                container.style.display = 'flex';
                this.clear();
                this.focusInput();
            }
        }

        close() {
            const container = document.getElementById(this.containerId);
            if (container && this.isModal) {
                container.style.display = 'none';
            }
            this.clear();
        }

        focusInput() {
            // Suppress mobile virtual keyboards on Android and iOS while allowing desktop keyboard capture
            const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0) || /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
            if (!isTouch) {
                setTimeout(() => {
                    const hiddenInput = document.getElementById(`paf-input-${this.instanceId}`);
                    if (hiddenInput) hiddenInput.focus();
                }, 100);
            }
        }

        pressKey(digit) {
            if (this.isVerifying || this.currentPin.length >= 4) return;
            this.currentPin += digit;
            this.updateDisplay();

            if (this.currentPin.length === 4) {
                this.lookupPin(this.currentPin);
            }
        }

        backspace() {
            if (this.isVerifying || this.currentPin.length === 0) return;
            this.currentPin = this.currentPin.slice(0, -1);
            this.updateDisplay();
            this.setStatus('Tap digits or use keyboard');
        }

        clear() {
            this.currentPin = '';
            this.activeAttendee = null;
            this.isVerifying = false;
            this.updateDisplay();
            this.setStatus('Tap digits or use keyboard');
            const hiddenInput = document.getElementById(`paf-input-${this.instanceId}`);
            if (hiddenInput) hiddenInput.value = '';
        }

        updateDisplay() {
            for (let i = 0; i < 4; i++) {
                const box = document.getElementById(`paf-box-${i}-${this.instanceId}`);
                if (!box) continue;
                if (i < this.currentPin.length) {
                    box.innerText = this.currentPin[i];
                    box.className = 'paf-digit-box filled';
                } else if (i === this.currentPin.length) {
                    box.innerText = '•';
                    box.className = 'paf-digit-box active';
                } else {
                    box.innerText = '•';
                    box.className = 'paf-digit-box';
                }
            }
            const hiddenInput = document.getElementById(`paf-input-${this.instanceId}`);
            if (hiddenInput && hiddenInput.value !== this.currentPin) {
                hiddenInput.value = this.currentPin;
            }
        }

        setStatus(msg, type = '') {
            const statusEl = document.getElementById(`paf-status-${this.instanceId}`);
            if (!statusEl) return;
            statusEl.innerText = msg;
            statusEl.className = 'paf-status-msg' + (type ? ` ${type}` : '');
        }

        async lookupPin(pin) {
            this.isVerifying = true;
            this.setStatus('Verifying attendee PIN...', '');

            try {
                const url = (this.apiHost || '') + '/api/attendee/lookup';
                const res = await fetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pin: pin })
                });

                const data = await res.json();

                if (res.ok && data.success) {
                    this.setStatus('✓ Attendee verified!', 'success');
                    this.activeAttendee = {
                        id: data.id || data.player_id,
                        display_name: data.display_name || 'Attendee',
                        email: data.email || 'N/A',
                        balance: Number(data.balance || 0),
                        pin: pin
                    };
                    setTimeout(() => {
                        this.showStep2Modal();
                    }, 200);
                } else {
                    const errMsg = (data && data.error) ? data.error : 'Invalid PIN';
                    this.setStatus(`❌ ${errMsg}`, 'error');
                    this.shakeBoxes();
                    setTimeout(() => {
                        this.clear();
                    }, 800);
                }
            } catch (err) {
                console.error('[PinAuthFlow] Lookup error:', err);
                this.setStatus('❌ Connection error verifying PIN.', 'error');
                this.shakeBoxes();
                setTimeout(() => {
                    this.clear();
                }, 900);
            } finally {
                this.isVerifying = false;
            }
        }

        shakeBoxes() {
            const boxes = document.getElementById(`paf-boxes-${this.instanceId}`);
            if (boxes) {
                boxes.style.animation = 'pafPulse 0.3s ease-in-out';
                setTimeout(() => {
                    boxes.style.animation = '';
                }, 300);
            }
        }

        setTokenCost(cost) {
            this.tokenCost = (cost !== null && cost !== undefined) ? Number(cost) : null;
            const pill = document.getElementById(`paf-cost-pill-${this.instanceId}`);
            if (pill) {
                if (this.tokenCost && this.tokenCost > 0) {
                    pill.innerText = `🪙 ${this.tokenCost} TOKENS TO PLAY`;
                    pill.style.display = 'inline-flex';
                } else {
                    pill.style.display = 'none';
                }
            }
        }

        showStep2Modal() {
            if (!this.activeAttendee) return;
            document.getElementById(`paf-confirm-name-${this.instanceId}`).innerText = this.activeAttendee.display_name;
            document.getElementById(`paf-confirm-email-${this.instanceId}`).innerText = this.activeAttendee.email || 'N/A';
            document.getElementById(`paf-confirm-balance-${this.instanceId}`).innerText = this.activeAttendee.balance;

            const costRow = document.getElementById(`paf-row-cost-${this.instanceId}`);
            const afterRow = document.getElementById(`paf-row-after-${this.instanceId}`);
            const confirmBtn = document.getElementById(`paf-btn-confirm-${this.instanceId}`);

            if (this.tokenCost && this.tokenCost > 0) {
                if (costRow) {
                    costRow.style.display = 'flex';
                    const costEl = document.getElementById(`paf-confirm-cost-${this.instanceId}`);
                    if (costEl) costEl.innerText = `-${this.tokenCost} Tokens`;
                }
                if (afterRow) {
                    afterRow.style.display = 'flex';
                    const afterBal = Math.max(0, this.activeAttendee.balance - this.tokenCost);
                    const afterEl = document.getElementById(`paf-confirm-after-${this.instanceId}`);
                    if (afterEl) afterEl.innerText = `${afterBal} Tokens`;
                }
                if (confirmBtn) {
                    if (this.activeAttendee.balance < this.tokenCost) {
                        confirmBtn.disabled = true;
                        confirmBtn.innerText = `Insufficient Tokens (${this.activeAttendee.balance}/${this.tokenCost})`;
                        confirmBtn.style.opacity = '0.5';
                        confirmBtn.style.cursor = 'not-allowed';
                    } else {
                        confirmBtn.disabled = false;
                        confirmBtn.innerText = `Confirm & Play (-${this.tokenCost} Tokens)`;
                        confirmBtn.style.opacity = '1';
                        confirmBtn.style.cursor = 'pointer';
                    }
                }
            } else {
                if (costRow) costRow.style.display = 'none';
                if (afterRow) afterRow.style.display = 'none';
                if (confirmBtn) {
                    confirmBtn.disabled = false;
                    confirmBtn.innerText = 'Confirm';
                    confirmBtn.style.opacity = '1';
                    confirmBtn.style.cursor = 'pointer';
                }
            }

            const modal = document.getElementById(`paf-confirm-modal-${this.instanceId}`);
            if (modal) modal.style.display = 'flex';
        }

        hideStep2Modal() {
            const modal = document.getElementById(`paf-confirm-modal-${this.instanceId}`);
            if (modal) modal.style.display = 'none';
        }

        onCancelClick() {
            this.hideStep2Modal();
            this.clear();
            if (typeof this.onCancel === 'function') {
                this.onCancel();
            }
        }

        onConfirmClick() {
            if (this.tokenCost && this.tokenCost > 0 && this.activeAttendee) {
                if (Number(this.activeAttendee.balance || 0) < this.tokenCost) {
                    const attendee = this.activeAttendee;
                    this.hideStep2Modal();
                    if (typeof this.onInsufficientTokens === 'function') {
                        this.onInsufficientTokens(attendee, this.tokenCost);
                    } else if (typeof this.onConfirmed === 'function') {
                        this.onConfirmed(attendee);
                    }
                    return;
                }
            }
            this.hideStep2Modal();
            if (this.isModal) {
                const container = document.getElementById(this.containerId);
                if (container) container.style.display = 'none';
            }
            const attendee = this.activeAttendee;
            this.activeAttendee = null;
            if (typeof this.onConfirmed === 'function') {
                this.onConfirmed(attendee);
            }
        }

        /**
         * Step 3 completion helper: wipes state and cleanly resets to Step 1.
         */
        resetToStep1() {
            this.hideStep2Modal();
            this.clear();
            const step1 = document.getElementById(`paf-step-1-${this.instanceId}`);
            if (step1) step1.style.display = 'flex';
            if (this.isModal) {
                const container = document.getElementById(this.containerId);
                if (container) container.style.display = 'none';
            }
        }
    }

    // Expose globally
    window.PinAuthFlow = PinAuthFlow;
})(window);
