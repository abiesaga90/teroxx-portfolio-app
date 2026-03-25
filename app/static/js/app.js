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
// Extended palette for per-position pie chart (25+ tokens)
const CHART_COLORS = [
    '#010626', '#0b688c', '#d06643', '#4A8FA4', '#bfb3a8', '#060d43',
    '#1a8a4a', '#8B5CF6', '#EC4899', '#F59E0B', '#06B6D4', '#84CC16',
    '#6366F1', '#EF4444', '#14B8A6', '#F97316', '#A855F7', '#22D3EE',
    '#E11D48', '#65A30D', '#7C3AED', '#DB2777', '#0EA5E9', '#D97706',
    '#059669', '#9333EA', '#DC2626', '#2563EB', '#CA8A04', '#16A34A',
];

let allocChart = null;
function renderAllocChart(labels, values) {
    const ctx = document.getElementById('alloc-chart');
    if (!ctx) return;
    if (allocChart) allocChart.destroy();

    const colors = CHART_COLORS.slice(0, labels.length);

    allocChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
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
            cutout: '60%',
        },
    });

    // Build custom legend with ticker + % for all positions
    const legendEl = document.getElementById('alloc-legend');
    if (legendEl) {
        legendEl.innerHTML = labels.map((label, i) => {
            const pct = (values[i] * 100).toFixed(1);
            const color = colors[i % colors.length];
            const isBig = values[i] >= 0.05; // highlight 5%+ allocations
            const weight = isBig ? 'font-weight:700;' : '';
            const size = isBig ? 'font-size:0.8125rem;' : 'font-size:0.6875rem;';
            return `<span class="legend-item" style="${weight}${size}">` +
                `<span class="legend-dot" style="background:${color};"></span>` +
                `${label} ${pct}%</span>`;
        }).join('');
    }
}

// ── Collapsible sections ──
function toggleCollapsible(btn) {
    const content = btn.nextElementSibling;
    const arrow = btn.querySelector('.collapsible-arrow');
    const isOpen = content.classList.toggle('open');
    if (arrow) arrow.style.transform = isOpen ? 'rotate(90deg)' : '';
}

// ── Render chart from embedded data ──
function tryRenderChart() {
    const chartData = document.getElementById('chart-data');
    if (chartData) {
        try {
            const data = JSON.parse(chartData.textContent);
            renderAllocChart(data.labels, data.values);
        } catch (e) {}
    }
}

// Initial page load — call immediately since script is at bottom of body
tryRenderAllCharts();

// After HTMX swaps — use afterSettle + rAF to ensure DOM is painted
document.addEventListener('htmx:afterSettle', function() {
    requestAnimationFrame(function() {
        setTimeout(tryRenderAllCharts, 20);
    });
});

// toggleTheme() and dark mode restore are defined inline in <head> of base.html
// so they work even if this script fails to load.

// ── Raw data toggle ──
function toggleRawData(ticker) {
    const row = document.getElementById('raw-' + ticker);
    if (row) row.style.display = row.style.display === 'none' ? '' : 'none';
}

// ── Theme-aware chart colors ──
function getChartColors() {
    const style = getComputedStyle(document.documentElement);
    return {
        text: style.getPropertyValue('--text-body').trim() || '#060D43',
        muted: style.getPropertyValue('--text-muted').trim() || 'rgba(6,13,67,0.45)',
        grid: style.getPropertyValue('--border').trim() || 'rgba(6,13,67,0.10)',
        card: style.getPropertyValue('--bg-card').trim() || '#ffffff',
    };
}

// ── Chart registry (for cleanup on HTMX swap) ──
const _charts = {};
function _destroyChart(id) {
    if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}

// ── Radar Chart (5-Factor Top Tokens) ──
function tryRenderRadar() {
    const el = document.getElementById('radar-data');
    if (!el) return;
    try {
        const data = JSON.parse(el.textContent);
        const ctx = document.getElementById('radar-chart');
        if (!ctx) return;
        _destroyChart('radar');
        const tc = getChartColors();
        const radarColors = ['#0b688c', '#d06643', '#010626', '#1a8a4a', '#8B5CF6'];
        const datasets = data.tokens.map((t, i) => ({
            label: t.ticker,
            data: t.scores,
            borderColor: radarColors[i % radarColors.length],
            backgroundColor: radarColors[i % radarColors.length] + '20',
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: radarColors[i % radarColors.length],
        }));
        _charts['radar'] = new Chart(ctx, {
            type: 'radar',
            data: { labels: data.factors, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { position: 'bottom', labels: { color: tc.text, font: { size: 11 }, padding: 15 } },
                },
                scales: {
                    r: {
                        min: 0, max: 100,
                        ticks: { display: false, stepSize: 25 },
                        grid: { color: tc.grid },
                        angleLines: { color: tc.grid },
                        pointLabels: { color: tc.text, font: { size: 10 } },
                    },
                },
            },
        });
    } catch (e) { console.warn('Radar chart error:', e); }
}

// ── Bubble Scatter (Risk/Return) ──
function tryRenderBubble() {
    const el = document.getElementById('bubble-data');
    if (!el) return;
    try {
        const data = JSON.parse(el.textContent);
        const ctx = document.getElementById('bubble-chart');
        if (!ctx) return;
        _destroyChart('bubble');
        const tc = getChartColors();
        const catColors = {
            'Layer 1': '#0b688c', 'DeFi': '#d06643', 'AI / Compute': '#8B5CF6',
            'Exchange': '#F59E0B', 'Infrastructure': '#06B6D4', 'Payment': '#84CC16',
            'Layer 2': '#6366F1', 'Meme': '#EC4899', 'Gaming': '#14B8A6',
            'Privacy': '#4A8FA4', 'Legacy': '#bfb3a8',
        };
        const points = data.tokens.map(t => ({
            x: t.vol, y: t.mom, r: Math.max(4, Math.min(25, Math.sqrt(t.mcap / 1e8))),
            label: t.ticker, category: t.cat,
        }));
        // Group by category
        const cats = {};
        points.forEach(p => {
            if (!cats[p.category]) cats[p.category] = [];
            cats[p.category].push(p);
        });
        const datasets = Object.entries(cats).map(([cat, pts]) => ({
            label: cat,
            data: pts,
            backgroundColor: (catColors[cat] || '#bfb3a8') + 'AA',
            borderColor: catColors[cat] || '#bfb3a8',
            borderWidth: 1,
        }));
        _charts['bubble'] = new Chart(ctx, {
            type: 'bubble',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { color: tc.text, font: { size: 10 }, padding: 10 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const p = ctx.raw;
                                return `${p.label}: Vol ${p.x.toFixed(0)}%, Mom ${p.y.toFixed(0)}%`;
                            },
                        },
                    },
                },
                scales: {
                    x: { title: { display: true, text: 'Volatility (|30d change|%)', color: tc.muted, font: { size: 10 } }, grid: { color: tc.grid }, ticks: { color: tc.muted, font: { size: 9 } } },
                    y: { title: { display: true, text: 'Momentum (7d+30d%)', color: tc.muted, font: { size: 10 } }, grid: { color: tc.grid }, ticks: { color: tc.muted, font: { size: 9 } } },
                },
            },
        });
    } catch (e) { console.warn('Bubble chart error:', e); }
}

// ── Dilution Bar Chart ──
function tryRenderDilution() {
    const el = document.getElementById('dilution-data');
    if (!el) return;
    try {
        const data = JSON.parse(el.textContent);
        const ctx = document.getElementById('dilution-chart');
        if (!ctx) return;
        _destroyChart('dilution');
        const tc = getChartColors();
        const colors = data.values.map(v => v < 2 ? '#1a8a4a' : v < 4 ? '#F59E0B' : '#c0432a');
        _charts['dilution'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{ data: data.values, backgroundColor: colors, borderRadius: 2 }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (ctx) => `FDV/MCap: ${ctx.raw.toFixed(2)}x` } },
                },
                scales: {
                    x: { title: { display: true, text: 'FDV / Market Cap Ratio', color: tc.muted, font: { size: 10 } }, grid: { color: tc.grid }, ticks: { color: tc.muted, font: { size: 9 } } },
                    y: { ticks: { color: tc.text, font: { size: 9 } }, grid: { display: false } },
                },
            },
        });
    } catch (e) { console.warn('Dilution chart error:', e); }
}

// ── DCA Accumulation Area Chart ──
function tryRenderDCA() {
    const el = document.getElementById('dca-chart-data');
    if (!el) return;
    try {
        const data = JSON.parse(el.textContent);
        const ctx = document.getElementById('dca-chart');
        if (!ctx) return;
        _destroyChart('dca');
        const tc = getChartColors();
        const areaColors = ['#0b688c', '#d06643', '#010626', '#1a8a4a', '#8B5CF6', '#F59E0B'];
        const datasets = data.series.map((s, i) => ({
            label: s.label,
            data: s.values,
            borderColor: areaColors[i % areaColors.length],
            backgroundColor: areaColors[i % areaColors.length] + '30',
            fill: true,
            tension: 0.3,
            pointRadius: 2,
            borderWidth: 2,
        }));
        _charts['dca'] = new Chart(ctx, {
            type: 'line',
            data: { labels: data.months, datasets },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom', labels: { color: tc.text, font: { size: 10 }, padding: 10 } } },
                scales: {
                    x: { title: { display: true, text: 'Month', color: tc.muted, font: { size: 10 } }, grid: { color: tc.grid }, ticks: { color: tc.muted } },
                    y: { title: { display: true, text: 'Cumulative ($)', color: tc.muted, font: { size: 10 } }, grid: { color: tc.grid }, ticks: { color: tc.muted, callback: v => '$' + v.toLocaleString() } },
                },
            },
        });
    } catch (e) { console.warn('DCA chart error:', e); }
}

// ── P&L Waterfall Chart ──
function tryRenderWaterfall() {
    const el = document.getElementById('pnl-chart-data');
    if (!el) return;
    try {
        const data = JSON.parse(el.textContent);
        const ctx = document.getElementById('pnl-chart');
        if (!ctx) return;
        _destroyChart('waterfall');
        const tc = getChartColors();
        const colors = data.values.map(v => v >= 0 ? '#1a8a4a' : '#c0432a');
        _charts['waterfall'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{ data: data.values, backgroundColor: colors, borderRadius: 2 }],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (ctx) => `P&L: $${ctx.raw.toFixed(2)}` } },
                },
                scales: {
                    x: { ticks: { color: tc.text, font: { size: 9 }, maxRotation: 45 }, grid: { display: false } },
                    y: { title: { display: true, text: 'P&L ($)', color: tc.muted, font: { size: 10 } }, grid: { color: tc.grid }, ticks: { color: tc.muted, callback: v => '$' + v.toLocaleString() } },
                },
            },
        });
    } catch (e) { console.warn('Waterfall chart error:', e); }
}

// ── Sector Stacked Bar ──
function tryRenderSector() {
    const el = document.getElementById('sector-data');
    if (!el) return;
    try {
        const data = JSON.parse(el.textContent);
        const ctx = document.getElementById('sector-chart');
        if (!ctx) return;
        _destroyChart('sector');
        const tc = getChartColors();
        const sectorColors = {
            'Store of Value': '#010626', 'Layer 1': '#0b688c', 'DeFi': '#d06643',
            'Exchange': '#F59E0B', 'Infrastructure': '#06B6D4', 'AI / Compute': '#8B5CF6',
            'Payment': '#84CC16', 'Layer 2': '#6366F1', 'Meme': '#EC4899',
            'Gaming': '#14B8A6', 'Privacy': '#4A8FA4', 'Gold Hedge': '#bfb3a8',
            'Stablecoin': '#9CA3AF', 'Legacy': '#78716C', 'Other': '#A3A3A3',
        };
        const datasets = data.categories.map(cat => ({
            label: cat,
            data: data.profiles.map(p => data.matrix[p]?.[cat] || 0),
            backgroundColor: sectorColors[cat] || '#bfb3a8',
        }));
        _charts['sector'] = new Chart(ctx, {
            type: 'bar',
            data: { labels: data.profiles, datasets },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom', labels: { color: tc.text, font: { size: 9 }, padding: 8 } },
                    tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${(ctx.raw * 100).toFixed(1)}%` } },
                },
                scales: {
                    x: { stacked: true, ticks: { color: tc.text, font: { size: 11 } }, grid: { display: false } },
                    y: { stacked: true, max: 1, ticks: { color: tc.muted, callback: v => (v * 100) + '%' }, grid: { color: tc.grid } },
                },
            },
        });
    } catch (e) { console.warn('Sector chart error:', e); }
}

// ── Token Scorecard Modal ──
function openTokenModal(ticker) {
    const modal = document.getElementById('token-modal');
    const backdrop = document.getElementById('token-modal-backdrop');
    const content = document.getElementById('token-modal-content');
    if (!modal || !content) return;

    content.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted)">Loading...</div>';
    modal.style.display = 'block';
    backdrop.style.display = 'block';
    document.body.style.overflow = 'hidden';

    fetch(`/api/token/${ticker}?profile=Balanced`)
        .then(r => r.text())
        .then(html => {
            content.innerHTML = html;
            // Render mini radar in modal
            tryRenderTokenRadar();
        })
        .catch(e => {
            content.innerHTML = `<div style="padding:40px;color:var(--danger)">Error loading ${ticker}</div>`;
        });
}

function closeTokenModal() {
    const modal = document.getElementById('token-modal');
    const backdrop = document.getElementById('token-modal-backdrop');
    if (modal) modal.style.display = 'none';
    if (backdrop) backdrop.style.display = 'none';
    document.body.style.overflow = '';
    _destroyChart('tokenRadar');
}

// Escape key closes modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeTokenModal();
});

function tryRenderTokenRadar() {
    const el = document.getElementById('token-radar-data');
    if (!el) return;
    try {
        const data = JSON.parse(el.textContent);
        const ctx = document.getElementById('token-radar-chart');
        if (!ctx) return;
        _destroyChart('tokenRadar');
        const tc = getChartColors();
        _charts['tokenRadar'] = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: data.factors.map(f => f.replace(/\(.*\)/, '').trim()),
                datasets: [
                    {
                        label: data.token_label,
                        data: data.token_scores,
                        borderColor: '#0b688c',
                        backgroundColor: 'rgba(11,104,140,0.15)',
                        borderWidth: 2,
                        pointRadius: 4,
                        pointBackgroundColor: '#0b688c',
                    },
                    {
                        label: 'Median',
                        data: data.median_scores,
                        borderColor: '#bfb3a8',
                        backgroundColor: 'rgba(191,179,168,0.08)',
                        borderWidth: 1.5,
                        borderDash: [4, 4],
                        pointRadius: 2,
                        pointBackgroundColor: '#bfb3a8',
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom', labels: { color: tc.text, font: { size: 10 } } } },
                scales: {
                    r: {
                        min: 0, max: 100,
                        ticks: { display: false, stepSize: 25 },
                        grid: { color: tc.grid },
                        angleLines: { color: tc.grid },
                        pointLabels: { color: tc.text, font: { size: 9 } },
                    },
                },
            },
        });
    } catch (e) { console.warn('Token radar error:', e); }
}

// ── Master render: try all charts ──
function tryRenderAllCharts() {
    tryRenderChart();  // existing donut
    tryRenderRadar();
    tryRenderBubble();
    tryRenderDilution();
    tryRenderDCA();
    tryRenderWaterfall();
    tryRenderSector();
}
