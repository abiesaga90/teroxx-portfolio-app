// Teroxx SessionContext shim — single namespace for in-page session state.
//
// Replaces the patchwork of localStorage / sessionStorage keys with one
// object that mirrors the server-side SessionContext (app/session_context.py).
// All advisor-mode tabs read from teroxx.session.ctx and call
// teroxx.session.patch({...}) to mutate it; the server is source of truth.
(function () {
    const NS = window.teroxx = window.teroxx || {};
    const SESSION_KEY = 'teroxx.session.ctx';

    const defaults = {
        user_email: null,
        mode: 'advisor',
        client_id: null,
        universe: 'Teroxx Core (9)',
        profile: 'Balanced',
        portfolio_value: 100000,
        as_of: null,
    };

    function readLocal() {
        try {
            const raw = localStorage.getItem(SESSION_KEY);
            return raw ? Object.assign({}, defaults, JSON.parse(raw)) : { ...defaults };
        } catch (e) {
            return { ...defaults };
        }
    }

    function writeLocal(ctx) {
        try { localStorage.setItem(SESSION_KEY, JSON.stringify(ctx)); } catch (e) {}
    }

    const session = {
        ctx: readLocal(),

        async load() {
            try {
                const resp = await fetch('/api/session', { credentials: 'same-origin' });
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                this.ctx = Object.assign({}, defaults, await resp.json());
                writeLocal(this.ctx);
            } catch (e) {
                console.warn('SessionContext load failed:', e);
            }
            return this.ctx;
        },

        async patch(updates) {
            // Optimistic local update so the UI doesn't flicker.
            this.ctx = Object.assign({}, this.ctx, updates);
            writeLocal(this.ctx);
            try {
                const resp = await fetch('/api/session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify(updates),
                });
                if (resp.ok) {
                    this.ctx = Object.assign({}, defaults, await resp.json());
                    writeLocal(this.ctx);
                }
            } catch (e) {
                console.warn('SessionContext patch failed:', e);
            }
            return this.ctx;
        },

        get(key) { return this.ctx[key]; },
    };

    NS.session = session;

    // Best-effort hydrate from the server right at boot; the inline
    // window.__INITIAL_CTX__ from base.html is the authoritative seed for
    // the first paint to avoid a flash.
    if (window.__INITIAL_CTX__) {
        session.ctx = Object.assign({}, defaults, window.__INITIAL_CTX__);
        writeLocal(session.ctx);
    } else {
        session.load();
    }
})();

// ── Mode switch handler ───────────────────────────────────────────────
function setAppMode(mode) {
    const valid = ['advisor', 'research', 'client_view'];
    if (!valid.includes(mode)) return;
    document.body.setAttribute('data-mode', mode);
    const sw = document.querySelector('.mode-switch');
    if (sw) sw.setAttribute('data-mode', mode);
    applyTabVisibility(mode);
    // If the currently active tab is no longer visible in this mode,
    // jump to the first visible tab.
    const activeBtn = document.querySelector('.tab-btn.active:not(.mode-hidden)');
    if (!activeBtn) {
        const firstVisible = document.querySelector('.tab-btn:not(.mode-hidden)');
        if (firstVisible) {
            const tabId = firstVisible.getAttribute('data-tab');
            if (tabId && typeof switchTab === 'function') switchTab(tabId);
        }
    }
    if (window.teroxx && window.teroxx.session) {
        window.teroxx.session.patch({ mode: mode });
    }
}

function applyTabVisibility(mode) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const modes = (btn.getAttribute('data-modes') || '').split(',').map(s => s.trim()).filter(Boolean);
        if (modes.length === 0 || modes.includes(mode)) {
            btn.classList.remove('mode-hidden');
        } else {
            btn.classList.add('mode-hidden');
        }
    });
}

// Run as early as possible so tabs render correctly for the seeded mode.
(function () {
    function init() {
        const initial = (window.__INITIAL_CTX__ && window.__INITIAL_CTX__.mode) || 'advisor';
        document.body.setAttribute('data-mode', initial);
        applyTabVisibility(initial);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
