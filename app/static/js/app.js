// ── Tab switching ──
function switchTab(tabId) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId)?.classList.add('active');
    document.querySelector(`[data-tab="${tabId}"]`)?.classList.add('active');
    localStorage.setItem('activeTab', tabId);
}

// Restore last tab on load
document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('activeTab');
    if (saved && document.getElementById(saved)) {
        switchTab(saved);
    }
});

// ── Shared state: profile, universe, mode ──
function getSharedParams() {
    const form = document.getElementById('global-controls');
    if (!form) return {};
    return {
        profile: form.querySelector('[name="profile"]')?.value || 'Balanced',
        universe: form.querySelector('[name="universe"]')?.value || 'Full (25)',
        mode: form.querySelector('[name="mode"]')?.value || 'Standard',
    };
}

// ── Donut chart rendering ──
// Teroxx brand chart palette order (from brand guidelines)
const CHART_COLORS = ['#010626', '#0b688c', '#d06643', '#4A8FA4', '#bfb3a8', '#060d43'];

let allocChart = null;
function renderAllocChart(labels, values) {
    const ctx = document.getElementById('alloc-chart');
    if (!ctx) return;
    if (allocChart) allocChart.destroy();

    allocChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: CHART_COLORS.slice(0, labels.length),
                borderColor: '#ffffff',
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.label}: ${(ctx.raw * 100).toFixed(1)}%`
                    }
                }
            },
            cutout: '65%',
        },
    });
}

// ── Rebalancing: save/load current holdings ──
function saveHoldings() {
    const inputs = document.querySelectorAll('.holding-input');
    const holdings = {};
    inputs.forEach(input => {
        const val = parseFloat(input.value) || 0;
        if (val > 0) holdings[input.dataset.ticker] = val;
    });
    localStorage.setItem('currentHoldings', JSON.stringify(holdings));
    return holdings;
}

function loadHoldings() {
    try {
        return JSON.parse(localStorage.getItem('currentHoldings') || '{}');
    } catch { return {}; }
}

// ── P&L: save/load positions ──
function savePositions() {
    const rows = document.querySelectorAll('.pnl-row');
    const positions = [];
    rows.forEach(row => {
        const ticker = row.dataset.ticker;
        const qty = parseFloat(row.querySelector('.pnl-qty')?.value) || 0;
        const entry = parseFloat(row.querySelector('.pnl-entry')?.value) || 0;
        if (qty > 0 && entry > 0) {
            positions.push({ ticker, quantity: qty, entry_price: entry });
        }
    });
    localStorage.setItem('pnlPositions', JSON.stringify(positions));
    return positions;
}

function loadPositions() {
    try {
        return JSON.parse(localStorage.getItem('pnlPositions') || '[]');
    } catch { return []; }
}

// ── HTMX event: after swap, re-render charts ──
document.addEventListener('htmx:afterSwap', (event) => {
    // Check if we need to render allocation donut
    const chartData = document.getElementById('chart-data');
    if (chartData) {
        try {
            const data = JSON.parse(chartData.textContent);
            renderAllocChart(data.labels, data.values);
        } catch (e) {}
    }
});
