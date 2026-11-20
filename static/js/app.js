/**
 * SellBundle Ghana - Client Application Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    const state = {
        activeTab: 'data-bundles',
        selectedNetwork: 'mtn',
        bundles: [],
        selectedBundle: null,
        checkers: [],
        selectedChecker: null,
        checkerQuantity: 1,
        networks: []
    };

    // DOM Elements
    const bundleGrid = document.getElementById('bundle-grid');
    const networkCards = document.querySelectorAll('.network-card');
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    const phoneInput = document.getElementById('customer-phone');
    const phoneHint = document.getElementById('phone-hint');
    const emailInput = document.getElementById('customer-email');
    const btnPay = document.getElementById('btn-pay-bundle');
    const orderSummaryBox = document.getElementById('order-summary-box');

    // Phone prefix mappings
    const PREFIXES = {
        mtn: ['024', '025', '053', '054', '055', '059'],
        telecel: ['020', '050'],
        at: ['027', '057', '026', '056', '028', '058']
    };

    // -------------------------------------------------------------------------
    // INITIALIZATION
    // -------------------------------------------------------------------------
    fetchNetworks();
    fetchBundles('mtn');
    fetchCheckers();
    handlePaymentReturn();

    // -------------------------------------------------------------------------
    // TAB SWITCHING
    // -------------------------------------------------------------------------
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const panel = document.getElementById(`tab-${target}`);
            if (panel) panel.classList.add('active');
            state.activeTab = target;
        });
    });

    // -------------------------------------------------------------------------
    // NETWORK SWITCHING
    // -------------------------------------------------------------------------
    networkCards.forEach(card => {
        card.addEventListener('click', () => {
            networkCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            const net = card.dataset.network;
            state.selectedNetwork = net;
            state.selectedBundle = null;
            updateSummary();
            fetchBundles(net);
        });
    });

    // -------------------------------------------------------------------------
    // PHONE NUMBER VALIDATION & PREFIX DETECTION
    // -------------------------------------------------------------------------
    phoneInput?.addEventListener('input', (e) => {
        const val = e.target.value.trim().replace(/\s+/g, '');
        detectNetworkPrefix(val);
        validateCheckoutButton();
    });

    emailInput?.addEventListener('input', () => {
        validateCheckoutButton();
    });

    function detectNetworkPrefix(phone) {
        if (!phoneHint) return;
        phoneHint.style.display = 'none';
        phoneHint.className = 'phone-network-hint';

        let clean = phone;
        if (clean.startsWith('+233')) clean = '0' + clean.slice(4);
        if (clean.startsWith('233')) clean = '0' + clean.slice(3);

        if (clean.length >= 3) {
            const prefix = clean.substring(0, 3);
            if (PREFIXES.mtn.includes(prefix)) {
                phoneHint.textContent = 'MTN Match';
                phoneHint.classList.add('hint-mtn');
                phoneHint.style.display = 'flex';
            } else if (PREFIXES.telecel.includes(prefix)) {
                phoneHint.textContent = 'Telecel Match';
                phoneHint.classList.add('hint-telecel');
                phoneHint.style.display = 'flex';
            } else if (PREFIXES.at.includes(prefix)) {
                phoneHint.textContent = 'AT Match';
                phoneHint.classList.add('hint-at');
                phoneHint.style.display = 'flex';
            }
        }
    }

    // -------------------------------------------------------------------------
    // API CALLS: BUNDLES & NETWORKS
    // -------------------------------------------------------------------------
    async function fetchNetworks() {
        try {
            const res = await fetch('/api/bundles/networks/');
            const data = await res.json();
            if (data.networks) {
                state.networks = data.networks;
            }
        } catch (err) {
            console.error('Error fetching networks:', err);
        }
    }

    async function fetchBundles(network) {
        if (!bundleGrid) return;
        bundleGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: var(--text-muted);">Loading bundles...</div>';

        try {
            const res = await fetch(`/api/bundles/?network=${network}`);
            const data = await res.json();
            state.bundles = data.bundles || [];
            renderBundles();
        } catch (err) {
            bundleGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: #ef4444;">Failed to load bundles. Please try again.</div>';
        }
    }

    function renderBundles() {
        if (!bundleGrid) return;
        if (state.bundles.length === 0) {
            bundleGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: var(--text-muted);">No active packages found for this network.</div>';
            return;
        }

        bundleGrid.innerHTML = state.bundles.map(b => {
            const isSelected = state.selectedBundle && state.selectedBundle.id === b.id;
            return `
                <div class="bundle-card ${isSelected ? 'selected' : ''}" data-id="${b.id}">
                    <span class="bundle-badge">${b.network_display}</span>
                    <div class="bundle-size">${b.data_label}</div>
                    <div class="bundle-price-row">
                        <span class="bundle-price-curr">GHS</span>
                        <span class="bundle-price-val">${parseFloat(b.selling_price).toFixed(2)}</span>
                    </div>
                </div>
            `;
        }).join('');

        bundleGrid.querySelectorAll('.bundle-card').forEach(card => {
            card.addEventListener('click', () => {
                const id = parseInt(card.dataset.id);
                state.selectedBundle = state.bundles.find(b => b.id === id);
                bundleGrid.querySelectorAll('.bundle-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                updateSummary();
                validateCheckoutButton();
            });
        });
    }

    function updateSummary() {
        const sumNet = document.getElementById('summary-network');
        const sumPkg = document.getElementById('summary-package');
        const sumAmt = document.getElementById('summary-amount');

        if (!state.selectedBundle) {
            if (sumNet) sumNet.textContent = state.selectedNetwork.toUpperCase();
            if (sumPkg) sumPkg.textContent = 'None selected';
            if (sumAmt) sumAmt.textContent = 'GHS 0.00';
            return;
        }

        if (sumNet) sumNet.textContent = state.selectedBundle.network_display;
        if (sumPkg) sumPkg.textContent = state.selectedBundle.name;
        if (sumAmt) sumAmt.textContent = `GHS ${parseFloat(state.selectedBundle.selling_price).toFixed(2)}`;
    }

    function validateCheckoutButton() {
        if (!btnPay) return;
        const phone = phoneInput ? phoneInput.value.trim() : '';
        const isValidPhone = /^(\+?233|0)[2-9]\d{8}$/.test(phone);
        const hasBundle = !!state.selectedBundle;
        btnPay.disabled = !(isValidPhone && hasBundle);
    }

    // -------------------------------------------------------------------------
    // BUNDLE PURCHASE ACTION
    // -------------------------------------------------------------------------
    btnPay?.addEventListener('click', async () => {
        if (!state.selectedBundle) return;
        const phone = phoneInput.value.trim();
        const email = emailInput ? emailInput.value.trim() : '';

        btnPay.disabled = true;
        btnPay.innerHTML = '<span>Processing order...</span>';

        try {
            const payload = {
                order_type: 'data_bundle',
                customer_phone: phone,
                customer_email: email || `${phone}@sellbundle.gh`,
                network: state.selectedNetwork,
                bundle_id: state.selectedBundle.id,
                callback_url: window.location.origin + window.location.pathname,
                auto_initialize_payment: true
            };

            const res = await fetch('/api/orders/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                alert('Error placing order: ' + JSON.stringify(data));
                btnPay.disabled = false;
                btnPay.innerHTML = '<span>Proceed to Payment</span>';
                return;
            }

            const orderRef = data.order.reference;
            const payment = data.payment;

            if (payment && payment.authorization_url) {
                // Open Paystack checkout
                window.location.href = payment.authorization_url;
            } else {
                // Navigate to order tracker
                showOrderTracker(orderRef);
            }

        } catch (err) {
            alert('Connection failed. Please try again: ' + err.message);
            btnPay.disabled = false;
            btnPay.innerHTML = '<span>Proceed to Payment</span>';
        }
    });

    // -------------------------------------------------------------------------
    // WAEC RESULT CHECKERS
    // -------------------------------------------------------------------------
    async function fetchCheckers() {
        const container = document.getElementById('checker-grid');
        if (!container) return;

        try {
            const res = await fetch('/api/orders/result-checkers/');
            const data = await res.json();
            state.checkers = data.result_checkers || [];
            renderCheckers();
        } catch (err) {
            container.innerHTML = '<p style="color: #ef4444;">Failed to load WAEC products.</p>';
        }
    }

    function renderCheckers() {
        const container = document.getElementById('checker-grid');
        if (!container) return;

        container.innerHTML = state.checkers.map(c => {
            const inStock = c.available_stock > 0;
            const isSelected = state.selectedChecker && state.selectedChecker.code === c.code;
            return `
                <div class="checker-card ${isSelected ? 'selected' : ''}" data-code="${c.code}">
                    <div class="checker-header">
                        <h4 class="checker-title">${c.name}</h4>
                        <span class="stock-badge ${inStock ? 'stock-in' : 'stock-out'}">
                            ${inStock ? `${c.available_stock} in stock` : 'Sold out'}
                        </span>
                    </div>
                    <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1rem;">${c.description}</p>
                    <div class="bundle-price-row">
                        <span class="bundle-price-curr">GHS</span>
                        <span class="bundle-price-val">${parseFloat(c.selling_price).toFixed(2)}</span>
                    </div>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.checker-card').forEach(card => {
            card.addEventListener('click', () => {
                const code = card.dataset.code;
                state.selectedChecker = state.checkers.find(c => c.code === code);
                container.querySelectorAll('.checker-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                updateCheckerSummary();
            });
        });
    }

    const checkerQtyInput = document.getElementById('checker-qty');
    checkerQtyInput?.addEventListener('input', (e) => {
        state.checkerQuantity = parseInt(e.target.value) || 1;
        updateCheckerSummary();
    });

    function updateCheckerSummary() {
        const sumName = document.getElementById('checker-sum-name');
        const sumTotal = document.getElementById('checker-sum-total');
        const btnChecker = document.getElementById('btn-pay-checker');

        if (!state.selectedChecker) {
            if (sumName) sumName.textContent = 'None selected';
            if (sumTotal) sumTotal.textContent = 'GHS 0.00';
            if (btnChecker) btnChecker.disabled = true;
            return;
        }

        const total = (parseFloat(state.selectedChecker.selling_price) * state.checkerQuantity).toFixed(2);
        if (sumName) sumName.textContent = `${state.selectedChecker.name} (x${state.checkerQuantity})`;
        if (sumTotal) sumTotal.textContent = `GHS ${total}`;
        if (btnChecker) btnChecker.disabled = state.selectedChecker.available_stock < state.checkerQuantity;
    }

    const btnPayChecker = document.getElementById('btn-pay-checker');
    btnPayChecker?.addEventListener('click', async () => {
        if (!state.selectedChecker) return;
        const phone = document.getElementById('checker-phone').value.trim();
        const email = document.getElementById('checker-email').value.trim();

        if (!phone) {
            alert('Please enter your recipient phone number.');
            return;
        }

        btnPayChecker.disabled = true;
        btnPayChecker.innerHTML = '<span>Processing...</span>';

        try {
            const payload = {
                order_type: 'result_checker',
                customer_phone: phone,
                customer_email: email || `${phone}@sellbundle.gh`,
                result_checker_data: {
                    checker_type_code: state.selectedChecker.code,
                    quantity: state.checkerQuantity
                },
                callback_url: window.location.origin + window.location.pathname,
                auto_initialize_payment: true
            };

            const res = await fetch('/api/orders/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                alert('Order error: ' + JSON.stringify(data));
                btnPayChecker.disabled = false;
                btnPayChecker.innerHTML = '<span>Buy Checkers Now</span>';
                return;
            }

            if (data.payment && data.payment.authorization_url) {
                window.location.href = data.payment.authorization_url;
            } else {
                showOrderTracker(data.order.reference);
            }
        } catch (err) {
            alert('Request failed: ' + err.message);
            btnPayChecker.disabled = false;
            btnPayChecker.innerHTML = '<span>Buy Checkers Now</span>';
        }
    });

    // -------------------------------------------------------------------------
    // MTN AFA REGISTRATION
    // -------------------------------------------------------------------------
    const btnSubmitAfa = document.getElementById('btn-submit-afa');
    btnSubmitAfa?.addEventListener('click', async () => {
        const fullName = document.getElementById('afa-fullname').value.trim();
        const phone = document.getElementById('afa-phone').value.trim();
        const cardPin = document.getElementById('afa-card').value.trim().toUpperCase();
        const town = document.getElementById('afa-town').value.trim();
        const occupation = document.getElementById('afa-occupation').value.trim();
        const email = document.getElementById('afa-email').value.trim();

        if (!fullName || !phone || !cardPin || !town || !occupation) {
            alert('Please fill in all required fields.');
            return;
        }

        btnSubmitAfa.disabled = true;
        btnSubmitAfa.innerHTML = '<span>Submitting Registration...</span>';

        try {
            const payload = {
                order_type: 'afa_registration',
                customer_phone: phone,
                customer_email: email || `${phone}@sellbundle.gh`,
                afa_data: {
                    full_name: fullName,
                    phone_number: phone,
                    ghana_card_number: cardPin,
                    town: town,
                    occupation: occupation
                },
                callback_url: window.location.origin + window.location.pathname,
                auto_initialize_payment: true
            };

            const res = await fetch('/api/orders/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                alert('Registration validation error: ' + JSON.stringify(data));
                btnSubmitAfa.disabled = false;
                btnSubmitAfa.innerHTML = '<span>Submit & Pay GHS 10.00</span>';
                return;
            }

            if (data.payment && data.payment.authorization_url) {
                window.location.href = data.payment.authorization_url;
            } else {
                showOrderTracker(data.order.reference);
            }
        } catch (err) {
            alert('Submission failed: ' + err.message);
            btnSubmitAfa.disabled = false;
            btnSubmitAfa.innerHTML = '<span>Submit & Pay GHS 10.00</span>';
        }
    });

    // -------------------------------------------------------------------------
    // ORDER TRACKER SCREEN & PAYMENT RETURN FLOW
    // -------------------------------------------------------------------------
    const btnTrack = document.getElementById('btn-track-order');
    const trackInput = document.getElementById('track-reference-input');
    const trackResult = document.getElementById('track-result');

    btnTrack?.addEventListener('click', () => {
        const ref = trackInput.value.trim();
        if (ref) fetchOrderStatus(ref);
    });

    function showOrderTracker(reference) {
        // Switch to track tab
        const trackTabBtn = document.querySelector('[data-tab="track"]');
        if (trackTabBtn) trackTabBtn.click();
        if (trackInput) trackInput.value = reference;
        fetchOrderStatus(reference);
    }

    async function handlePaymentReturn() {
        const urlParams = new URLSearchParams(window.location.search);
        const ref = urlParams.get('reference') || urlParams.get('trxref');
        if (!ref) return;

        // Clean query parameters from URL so refreshes don't re-trigger
        try {
            window.history.replaceState({}, document.title, window.location.pathname);
        } catch (e) {}

        // Switch to track tab immediately
        const trackTabBtn = document.querySelector('[data-tab="track"]');
        if (trackTabBtn) trackTabBtn.click();
        if (trackInput) trackInput.value = ref;

        // Display verifying banner
        if (trackResult) {
            trackResult.innerHTML = `
                <div class="verifying-card">
                    <div class="spinner"></div>
                    <div>
                        <h4 style="margin-bottom: 0.25rem; font-weight: 700; color: #fff;">Verifying Payment with Paystack...</h4>
                        <p style="font-size: 0.85rem; color: var(--text-secondary);">Confirming Mobile Money transaction for order <code>${ref}</code>. Please wait...</p>
                    </div>
                </div>
            `;
        }

        try {
            // Call payment verification endpoint
            await fetch(`/api/payments/verify/${encodeURIComponent(ref)}/`);
        } catch (err) {
            console.warn('Payment verification call error:', err);
        }

        // Fetch order status and poll until completed
        fetchOrderStatus(ref, true, 0);
    }

    async function fetchOrderStatus(reference, autoPoll = false, pollCount = 0) {
        if (!trackResult) return;
        if (!autoPoll || pollCount === 0) {
            trackResult.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 1.5rem;">Querying order status...</p>';
        }

        try {
            const res = await fetch(`/api/orders/${reference}/`);
            const data = await res.json();

            if (!res.ok) {
                trackResult.innerHTML = `
                    <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 1.25rem; border-radius: var(--radius-sm); color: #f87171;">
                        ${data.error || 'Order not found. Please check your reference code.'}
                    </div>
                `;
                return;
            }

            // Render status details
            const isVouchersAvailable = data.vouchers && data.vouchers.length > 0;
            const vouchersAllText = isVouchersAvailable
                ? data.vouchers.map((v, i) => `${i + 1}. [${v.type || data.checker_type_code || 'WAEC'}] Serial: ${v.serial_number} | PIN: ${v.pin}`).join('\\n')
                : '';

            const whatsappShareText = encodeURIComponent(
                `*SellBundle Ghana - Order Receipt*\\n` +
                `Order: ${data.reference}\\n` +
                `Product: ${data.order_type_display}${data.bundle_name ? ' - ' + data.bundle_name : ''}${data.checker_type_name ? ' - ' + data.checker_type_name : ''}\\n` +
                `Total: GHS ${parseFloat(data.amount).toFixed(2)}\\n` +
                (isVouchersAvailable ? `\\n*Vouchers Dispensed:*\\n${vouchersAllText}\\n` : '') +
                `\\nThank you for choosing SellBundle!`
            );

            const vouchersHtml = isVouchersAvailable ? `
                <div class="voucher-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <h4 style="color: var(--accent-green); font-weight: 700; margin: 0;">Digital Vouchers Dispensed:</h4>
                        <span style="font-size: 0.8rem; color: var(--text-muted);">${data.vouchers.length} unit(s)</span>
                    </div>
                    ${data.vouchers.map((v, idx) => `
                        <div class="voucher-item">
                            <div class="voucher-code-wrap">
                                <span class="voucher-serial-display">#${idx + 1} Serial: <strong>${v.serial_number}</strong></span>
                                <span class="voucher-pin-display">PIN: ${v.pin}</span>
                            </div>
                            <button type="button" class="btn-copy" data-copy="Serial: ${v.serial_number} | PIN: ${v.pin}">Copy</button>
                        </div>
                    `).join('')}
                    <div class="voucher-actions">
                        <button type="button" class="btn-receipt-action btn-copy-all" id="btn-copy-all-vouchers">
                            📋 Copy All PINs
                        </button>
                        <a href="https://api.whatsapp.com/send?text=${whatsappShareText}" target="_blank" rel="noopener" class="btn-receipt-action btn-whatsapp">
                            💬 Share on WhatsApp
                        </a>
                        <button type="button" class="btn-receipt-action btn-print" onclick="window.print()">
                            🖨️ Print Receipt
                        </button>
                    </div>
                </div>
            ` : '';

            // Failure notice if order failed
            const failureHtml = data.status === 'failed' ? `
                <div style="margin-top: 1rem; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.3); padding: 1rem; border-radius: var(--radius-sm); color: #fca5a5;">
                    <strong>Fulfillment Notice:</strong> ${data.failure_reason || 'We encountered an error processing your delivery. Our support team has been notified.'}
                </div>
            ` : '';

            // Auto-polling indicator if still in progress
            const isStillProcessing = data.status === 'processing' || data.status === 'paid';
            const pollingNoticeHtml = isStillProcessing && autoPoll ? `
                <div style="display: flex; align-items: center; gap: 0.6rem; margin-top: 1rem; font-size: 0.85rem; color: var(--accent-blue);">
                    <div class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
                    <span>Delivery in progress. Auto-updating live...</span>
                </div>
            ` : '';

            // Pending payment button for sandbox testing
            const payButtonHtml = data.status === 'pending_payment' ? `
                <div style="margin-top: 1.25rem;">
                    <a href="/sandbox/paystack/${data.reference}/" class="btn-primary" style="text-decoration: none; text-align: center; justify-content: center; width: 100%;">
                        💳 Complete MoMo Payment (Sandbox Simulator)
                    </a>
                </div>
            ` : '';

            trackResult.innerHTML = `
                <div class="tracker-status-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                        <span style="font-family: monospace; font-size: 1.1rem; font-weight: 700; color: #fff;">${data.reference}</span>
                        <span class="status-badge status-${data.status}">${data.status_display}</span>
                    </div>
                    <div class="summary-row">
                        <span>Product Type</span>
                        <span style="color: #fff; font-weight: 600;">${data.order_type_display}</span>
                    </div>
                    <div class="summary-row">
                        <span>Recipient Phone</span>
                        <span style="color: #fff; font-weight: 600;">${data.customer_phone}</span>
                    </div>
                    ${data.bundle_name ? `
                    <div class="summary-row">
                        <span>Package</span>
                        <span style="color: #fff; font-weight: 600;">${data.bundle_name}</span>
                    </div>` : ''}
                    ${data.checker_type_name ? `
                    <div class="summary-row">
                        <span>Checker Type</span>
                        <span style="color: #fff; font-weight: 600;">${data.checker_type_name} (${data.quantity}x)</span>
                    </div>` : ''}
                    <div class="summary-row">
                        <span>Total Payable</span>
                        <span style="color: var(--accent-gold); font-weight: 700;">GHS ${parseFloat(data.amount).toFixed(2)}</span>
                    </div>
                    <div class="summary-row">
                        <span>Date Ordered</span>
                        <span style="color: var(--text-muted);">${new Date(data.created_at).toLocaleString()}</span>
                    </div>
                    ${payButtonHtml}
                    ${failureHtml}
                    ${pollingNoticeHtml}
                    ${vouchersHtml}
                </div>
            `;

            // Attach copy listeners
            trackResult.querySelectorAll('.btn-copy').forEach(btn => {
                btn.addEventListener('click', () => {
                    const text = btn.dataset.copy;
                    navigator.clipboard.writeText(text).then(() => {
                        const original = btn.textContent;
                        btn.textContent = '✓ Copied!';
                        btn.style.color = '#10b981';
                        setTimeout(() => {
                            btn.textContent = original;
                            btn.style.color = '';
                        }, 2000);
                    });
                });
            });

            const btnCopyAll = trackResult.querySelector('#btn-copy-all-vouchers');
            btnCopyAll?.addEventListener('click', () => {
                navigator.clipboard.writeText(vouchersAllText).then(() => {
                    btnCopyAll.textContent = '✓ All Vouchers Copied!';
                    setTimeout(() => {
                        btnCopyAll.textContent = '📋 Copy All PINs';
                    }, 2000);
                });
            });

            // Auto-polling: If order is processing/paid and autoPoll is requested, poll up to 8 times
            if (isStillProcessing && autoPoll && pollCount < 8) {
                setTimeout(() => {
                    fetchOrderStatus(reference, true, pollCount + 1);
                }, 2500);
            }

        } catch (err) {
            trackResult.innerHTML = '<p style="color: #ef4444;">Network error querying order status.</p>';
        }
    }
});
