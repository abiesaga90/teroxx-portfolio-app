// Teroxx SessionContext shim — single namespace for in-page session state.
//
// Replaces the patchwork of localStorage / sessionStorage keys with one
// object that mirrors the server-side SessionContext (app/session_context.py).
// The shim does NOT drive navigation any more (we run a single flat tab
// strip); it just keeps client_id / universe / profile / portfolio_value
// in sync between the browser and the server.
(function () {
    const NS = window.teroxx = window.teroxx || {};
    const SESSION_KEY = 'teroxx.session.ctx';

    const defaults = {
        user_email: null,
        mode: null,
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

    if (window.__INITIAL_CTX__) {
        session.ctx = Object.assign({}, defaults, window.__INITIAL_CTX__);
        writeLocal(session.ctx);
    } else {
        session.load();
    }
})();

// Backwards-compatible no-ops kept so older inline scripts cached in the
// browser do not throw. Master modes are no longer used; the nav is a
// single flat strip.
function setAppMode(_mode) { /* no-op */ }
function applyTabVisibility(_mode) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('mode-hidden'));
}
