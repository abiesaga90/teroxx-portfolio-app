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
    // Map old tab IDs to new ones for users with stale localStorage
    const tabMap = {
        'tab-allocator': 'tab-portfolio',
        'tab-factors': 'tab-scoring',
        'tab-fundamentals': 'tab-scoring',
        'tab-allocations': 'tab-portfolio',
        'tab-rebalancing': 'tab-rebalance-pnl',
        'tab-pnl': 'tab-rebalance-pnl',
    };
    const mapped = tabMap[saved] || saved;
    if (mapped && document.getElementById(mapped)) {
        switchTab(mapped);
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

// ── Collapsible sections ──
function toggleCollapsible(btn) {
    const content = btn.nextElementSibling;
    const arrow = btn.querySelector('.collapsible-arrow');
    const isOpen = content.classList.toggle('open');
    if (arrow) arrow.style.transform = isOpen ? 'rotate(90deg)' : '';
}

// ── HTMX event: after swap, re-render charts ──
document.addEventListener('htmx:afterSwap', (event) => {
    const chartData = document.getElementById('chart-data');
    if (chartData) {
        try {
            const data = JSON.parse(chartData.textContent);
            renderAllocChart(data.labels, data.values);
        } catch (e) {}
    }
});
