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
//
// Three master modes (Advisor / Research / Client View) drive what
// sub-tabs are visible. Each tab has a single canonical mode via
// data-primary-mode; tabs whose mode doesn't match the current master
// are hidden. Switching modes also jumps to that mode's home tab so
// the panel below the strip stays in step.

const MODE_HOME_TABS = {
    advisor: 'tab-workspace',
    research: 'tab-portfolio',
    client_view: 'tab-client-review',
};

function setAppMode(mode) {
    const valid = ['advisor', 'research', 'client_view'];
    if (!valid.includes(mode)) return;
    document.body.setAttribute('data-mode', mode);
    const sw = document.querySelector('.mode-switch');
    if (sw) sw.setAttribute('data-mode', mode);
    applyTabVisibility(mode);
    // If the currently active tab is hidden in the new mode, jump to
    // that mode's home tab so the user is never left looking at a panel
    // they cannot navigate back to.
    const activeBtn = document.querySelector('.tab-btn.active');
    const stillVisible = activeBtn && !activeBtn.classList.contains('mode-hidden');
    if (!stillVisible) {
        const home = MODE_HOME_TABS[mode];
        if (home && typeof switchTab === 'function') switchTab(home);
    }
    if (window.teroxx && window.teroxx.session) {
        window.teroxx.session.patch({ mode: mode });
    }
}

function applyTabVisibility(mode) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const primary = btn.getAttribute('data-primary-mode') || '';
        if (!primary || primary === mode) {
            btn.classList.remove('mode-hidden');
        } else {
            btn.classList.add('mode-hidden');
        }
    });
}

// Pick the right master mode for a given tab. Used by smart restore so
// returning users who closed the app on, say, the Scoring tab are
// dropped into Research mode automatically rather than into an empty
// Advisor screen.
function modeForTab(tabId) {
    const btn = document.querySelector(`[data-tab="${tabId}"]`);
    return btn?.getAttribute('data-primary-mode') || null;
}

// On first paint, reconcile the seeded mode against the user's last
// active tab. If the saved tab belongs to a different mode, switch the
// master mode first so the strip lines up with the tab being restored.
(function () {
    function init() {
        const ctxMode = (window.__INITIAL_CTX__ && window.__INITIAL_CTX__.mode) || 'advisor';
        const savedTab = (function () {
            try { return localStorage.getItem('activeTab'); } catch (_) { return null; }
        })();
        let mode = ctxMode;
        if (savedTab) {
            const owner = modeForTab(savedTab);
            if (owner && owner !== mode) {
                mode = owner;
                if (window.teroxx && window.teroxx.session) {
                    window.teroxx.session.patch({ mode: mode });
                }
            }
        }
        document.body.setAttribute('data-mode', mode);
        const sw = document.querySelector('.mode-switch');
        if (sw) sw.setAttribute('data-mode', mode);
        applyTabVisibility(mode);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
