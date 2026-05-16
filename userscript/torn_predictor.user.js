// ==UserScript==
// @name         Torn Battle Stats Predictor (TBSP)
// @namespace    https://tbsp.app
// @version      0.3.4
// @description  Predicts player battle stats using ML. Free & open alternative to BSP.
// @author       TBSP
// @match        https://www.torn.com/profiles.php*
// @match        https://www.torn.com/factions.php*
// @match        https://www.torn.com/halloffame.php*
// @match        https://www.torn.com/index.php?page=people*
// @match        https://www.torn.com/bounties.php*
// @match        https://www.torn.com/hospitalview.php*
// @match        https://www.torn.com/forums.php*
// @match        https://www.torn.com/page.php*
// @match        https://www.torn.com/joblist.php*
// @match        https://www.torn.com/competition.php*
// @match        https://www.torn.com/pmarket.php*
// @match        https://www.torn.com/properties.php*
// @match        https://www.torn.com/war.php*
// @match        https://www.torn.com/loader.php?sid=attack*
// @match        https://www.torn.com/page.php?sid=list&type=friends
// @match        https://www.torn.com/page.php?sid=list&type=enemies
// @match        https://www.torn.com/page.php?sid=list&type=targets
// @grant        GM_xmlhttpRequest
// @connect      torn-predictor-production.up.railway.app
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // =========================================================================
    // CONFIG
    // =========================================================================

    const SERVER = 'https://torn-predictor-production.up.railway.app';
    const CACHE_TTL_MS     = 7 * 24 * 60 * 60 * 1000;  // 7 days  (hard expiry — discard)
    const CACHE_REFRESH_MS = 1 * 24 * 60 * 60 * 1000;  // 1 day   (stale — refresh in background)

    // NPC IDs — never predict these
    const NPC_IDS = new Set([4, 7, 8, 9, 10, 15, 17, 19, 20, 21, 23]);

    // =========================================================================
    // STORAGE  (namespace: tbsp.)
    // =========================================================================

    const S = {
        get:    (k, fallback = null) => { try { return JSON.parse(localStorage.getItem('tbsp.' + k)); } catch { return fallback; } },
        set:    (k, v)  => localStorage.setItem('tbsp.' + k, JSON.stringify(v)),
        remove: (k)     => localStorage.removeItem('tbsp.' + k),
    };

    const getToken    = ()      => S.get('token');
    const setToken    = (t)     => S.set('token', t);
    const getMyTBS    = ()      => S.get('myTbs', 0);
    const setMyTBS    = (v)     => S.set('myTbs', v);
    const getMyTornId = ()      => S.get('myTornId');
    const setMyTornId = (v)     => S.set('myTornId', v);

    // Prediction cache
    function getCached(targetId) {
        const entry = S.get('pred.' + targetId);
        if (!entry) return null;
        if (Date.now() > entry.expires) { S.remove('pred.' + targetId); return null; }
        return entry;
    }
    function setCached(targetId, data) {
        S.set('pred.' + targetId, { ...data, expires: Date.now() + CACHE_TTL_MS, refreshed_at: Date.now() });
    }
    function isStale(entry) {
        return !entry.refreshed_at || Date.now() - entry.refreshed_at > CACHE_REFRESH_MS;
    }

    // Re-renders every visible badge using the current myTBS value.
    // Called whenever myTBS changes so colours stay in sync.
    function refreshAllBadgeColors() {
        document.querySelectorAll('.tbsp-badge[data-tbsp-id]').forEach(badge => {
            const id = parseInt(badge.dataset.tbspId, 10);
            const cached = getCached(id);
            if (cached) updateBadge(badge, cached);
        });
    }

    // IDs currently being refreshed — prevents duplicate concurrent requests
    const _refreshing = new Set();

    async function refreshInBackground(targetId) {
        if (_refreshing.has(targetId)) return;
        _refreshing.add(targetId);
        try {
            const res = await apiRequest(`/api/predict/${targetId}`);
            if (!res.ok) return;
            const data = await res.json();
            setCached(targetId, data);
            // Update every visible badge for this player without a page reload
            document.querySelectorAll(`.tbsp-badge[data-tbsp-id="${targetId}"]`).forEach(badge => {
                updateBadge(badge, data);
            });
            // If own prediction refreshed, update myTBS and re-colour all badges
            if (targetId === getMyTornId() && data.predicted_tbs) {
                setMyTBS(data.predicted_tbs);
                refreshAllBadgeColors();
            }
        } catch {}
        finally { _refreshing.delete(targetId); }
    }

    // =========================================================================
    // API  (GM_xmlhttpRequest bypasses CORS — requests come from the extension)
    // =========================================================================

    function gmFetch(url, opts = {}) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method:  opts.method || 'GET',
                url,
                headers: opts.headers || {},
                data:    opts.body   || null,
                timeout: 15000,
                onload(r) {
                    resolve({
                        ok:     r.status >= 200 && r.status < 300,
                        status: r.status,
                        json:   () => { try { return Promise.resolve(JSON.parse(r.responseText)); } catch(e) { return Promise.reject(e); } },
                    });
                },
                onerror()   { reject(new Error('Network error — check your connection')); },
                ontimeout() { reject(new Error('Request timed out')); },
            });
        });
    }

    async function apiRequest(path, opts = {}) {
        const token = getToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = 'Bearer ' + token;
        return gmFetch(SERVER + path, { ...opts, headers });
    }

    async function login(apiKey) {
        const res = await apiRequest('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ api_key: apiKey }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Login failed');
        }
        return res.json();
    }

    async function fetchPrediction(targetId) {
        const cached = getCached(targetId);
        if (cached) {
            if (isStale(cached)) refreshInBackground(targetId);
            return cached;
        }

        const res = await apiRequest(`/api/predict/${targetId}`);
        if (!res.ok) return null;

        const data = await res.json();
        setCached(targetId, data);
        // Keep myTBS in sync whenever a fresh server result arrives for own ID
        if (targetId === getMyTornId() && data.predicted_tbs) {
            setMyTBS(data.predicted_tbs);
        }
        return data;
    }

    async function uploadAttacks() {
        const res = await apiRequest('/api/data/upload-attacks', { method: 'POST' });
        return res.ok ? res.json() : null;
    }

    async function fetchSubscriptionStatus() {
        const res = await apiRequest('/api/subscription/status');
        return res.ok ? res.json() : null;
    }

    async function checkPayments() {
        const res = await apiRequest('/api/subscription/check-payments', { method: 'POST' });
        return res.ok ? res.json() : null;
    }

    // =========================================================================
    // COLOURS & BADGE TEXT  (from CLAUDE.md)
    // =========================================================================

    const COLOR_THRESHOLDS = [
        { maxPercent: 5,        color: '#949494', label: 'Very Weak'   },
        { maxPercent: 35,       color: '#FFFFFF', label: 'Weak'        },
        { maxPercent: 75,       color: '#73DF5D', label: 'Moderate'    },
        { maxPercent: 125,      color: '#47A6FF', label: 'Strong'      },
        { maxPercent: 400,      color: '#FFB30F', label: 'Very Strong' },
        { maxPercent: Infinity, color: '#FF0000', label: 'Dangerous'   },
    ];

    function getColor(targetTBS, myTBS) {
        if (!myTBS || myTBS === 0) return COLOR_THRESHOLDS[3]; // default: Strong (blue)
        const pct = (targetTBS / myTBS) * 100;
        return COLOR_THRESHOLDS.find(t => pct <= t.maxPercent) || COLOR_THRESHOLDS[5];
    }

    function formatTBS(tbs) {
        if (tbs >= 1_000_000_000) return (tbs / 1e9).toFixed(1) + 'B';
        if (tbs >= 1_000_000)     return (tbs / 1e6).toFixed(1) + 'M';
        if (tbs >= 1_000)         return Math.round(tbs / 1e3) + 'K';
        return String(tbs);
    }

    function badgeText(prediction, myTBS) {
        const { color, label } = getColor(prediction.predicted_tbs, myTBS);
        const samples  = prediction.training_samples || 0;
        const readable = formatTBS(prediction.predicted_tbs);
        let text;
        if (prediction.method === 'rank' || samples < 100) {
            text = label;                        // Phase 1: label only
        } else if (samples < 500) {
            text = `${label} ~${readable}`;      // Phase 2: approximate
        } else {
            text = `${label} ${readable}`;       // Phase 3: precise
        }
        return { text, color };
    }

    // =========================================================================
    // TOOLTIP
    // =========================================================================

    let tooltip = null;

    function createTooltip() {
        const el = document.createElement('div');
        el.id = 'tbsp-tooltip';
        el.style.cssText = `
            position: fixed; z-index: 99999; pointer-events: none; display: none;
            background: #1a1a2e; border: 1px solid #444; border-radius: 6px;
            padding: 8px 12px; font-size: 12px; color: #eee; line-height: 1.6;
            box-shadow: 0 4px 12px rgba(0,0,0,.6); min-width: 160px;
        `;
        document.body.appendChild(el);
        return el;
    }

    function showTooltip(e, prediction) {
        if (!tooltip) tooltip = createTooltip();
        const { label } = getColor(prediction.predicted_tbs, getMyTBS());
        const method = { rank: 'Rank estimate', ml: 'ML model', ml_fallback: 'ML (fallback)', spy: 'Spy data' }[prediction.method] || prediction.method;
        const conf   = { low: 'Low', medium: 'Medium', high: 'High' }[prediction.confidence] || prediction.confidence;
        tooltip.innerHTML = `
            <b>${prediction.target_name || prediction.target_id}</b><br>
            TBS: <b>${formatTBS(prediction.predicted_tbs)}</b> <span style="color:#aaa">(${label})</span><br>
            STR: ${formatTBS(prediction.predicted_str || 0)} &nbsp;
            DEF: ${formatTBS(prediction.predicted_def || 0)}<br>
            SPD: ${formatTBS(prediction.predicted_spd || 0)} &nbsp;
            DEX: ${formatTBS(prediction.predicted_dex || 0)}<br>
            <span style="color:#888">Method: ${method} &bull; Accuracy: ${conf}</span>
        `;
        tooltip.style.display = 'block';
        positionTooltip(e);
    }

    function positionTooltip(e) {
        if (!tooltip) return;
        const x = Math.min(e.clientX + 12, window.innerWidth  - 180);
        const y = Math.min(e.clientY + 12, window.innerHeight - 120);
        tooltip.style.left = x + 'px';
        tooltip.style.top  = y + 'px';
    }

    function hideTooltip() {
        if (tooltip) tooltip.style.display = 'none';
    }

    // =========================================================================
    // BADGE ELEMENT
    // =========================================================================

    function createBadge(prediction) {
        const myTBS = getMyTBS();
        const { text, color } = badgeText(prediction, myTBS);

        const badge = document.createElement('span');
        badge.className    = 'tbsp-badge';
        badge.dataset.tbspId = String(prediction.target_id);
        badge.textContent  = `[${text}]`;
        badge.style.cssText = `
            display: inline-block; margin-left: 4px;
            font-size: 11px; font-weight: bold;
            color: ${color}; cursor: help;
            text-shadow: 0 0 4px rgba(0,0,0,.8);
        `;

        badge.addEventListener('mousemove',  e => { showTooltip(e, prediction); positionTooltip(e); });
        badge.addEventListener('mouseleave', hideTooltip);

        return badge;
    }

    function updateBadge(badge, prediction) {
        const myTBS = getMyTBS();
        const { text, color } = badgeText(prediction, myTBS);
        badge.textContent  = `[${text}]`;
        badge.style.color  = color;
    }

    // =========================================================================
    // PAGE TYPE DETECTION
    // =========================================================================

    function getPageType() {
        const href = window.location.href;
        if (/profiles\.php/.test(href))               return 'profile';
        if (/loader\.php\?sid=attack/.test(href))     return 'attack';
        if (/factions\.php/.test(href))               return 'faction';
        if (/halloffame\.php/.test(href))             return 'hof';
        if (/bounties\.php/.test(href))               return 'bounty';
        if (/hospitalview\.php/.test(href))           return 'hospital';
        if (/war\.php/.test(href))                    return 'war';
        if (/forums\.php/.test(href))                 return 'forum';
        return 'list';
    }

    function getProfileTargetId() {
        const params = new URLSearchParams(window.location.search);
        return parseInt(params.get('XID') || '0', 10);
    }

    function getAttackTargetId() {
        const params = new URLSearchParams(window.location.search);
        return parseInt(params.get('user2ID') || '0', 10);
    }

    // =========================================================================
    // DOM HELPERS
    // =========================================================================

    // Extract torn ID from an element or its nearest link
    function parseTornId(el) {
        // el might be an <a> directly, or a container with an <a> inside/above
        const candidates = [];
        if (el.tagName === 'A') candidates.push(el);
        const inner = el.querySelector('a[href]');
        if (inner) candidates.push(inner);
        const outer = el.closest('a[href]');
        if (outer) candidates.push(outer);

        for (const a of candidates) {
            const href = a.href || '';
            const m = href.match(/(?:XID|user2ID|userID)=(\d+)/);
            if (m) return parseInt(m[1], 10);
        }
        return null;
    }

    function hasInjectedBadge(el) {
        return el.dataset.tbspDone === '1' || !!el.querySelector('.tbsp-badge');
    }

    function isInChat(el) {
        return !!el.closest('#chatRoot, .chat-box-wrap, [class*="chatBox"], [class*="chat-box"], [id*="chat"]');
    }

    // =========================================================================
    // INJECT BADGE — generic (list pages / inline)
    // =========================================================================

    async function injectBadge(nameEl) {
        if (hasInjectedBadge(nameEl)) return;
        if (isInChat(nameEl)) return;
        nameEl.dataset.tbspDone = '1';

        const targetId = parseTornId(nameEl);
        if (!targetId || NPC_IDS.has(targetId) || targetId === getMyTornId()) return;

        const placeholder = document.createElement('span');
        placeholder.className  = 'tbsp-badge';
        placeholder.dataset.tbspId = String(targetId);
        placeholder.textContent   = '[…]';
        placeholder.style.cssText = 'display:inline-block;margin-left:4px;font-size:11px;color:#666;';

        // Append inside container, or after the element if it's an <a>
        if (nameEl.tagName === 'A') {
            nameEl.insertAdjacentElement('afterend', placeholder);
        } else {
            nameEl.appendChild(placeholder);
        }

        const prediction = await fetchPrediction(targetId);
        if (!prediction) { placeholder.remove(); return; }

        const badge = createBadge(prediction);
        placeholder.replaceWith(badge);
    }

    // =========================================================================
    // INJECT — profile page (larger display block)
    // =========================================================================

    async function injectProfileBadge(targetId) {
        if (NPC_IDS.has(targetId)) return;
        if (document.getElementById('tbsp-profile-block')) return;

        const prediction = await fetchPrediction(targetId);
        if (!prediction) return;

        // Try multiple selectors for where to anchor the block
        const anchor =
            document.querySelector('.profile-wrapper') ||
            document.querySelector('.basic-info') ||
            document.querySelector('[class*="basicInfo"]') ||
            document.querySelector('[class*="profile-info"]') ||
            document.querySelector('.info-table') ||
            document.querySelector('.player-info-table') ||
            document.querySelector('h4.profile');

        if (!anchor) return;

        const myTBS = getMyTBS();
        const { text, color } = badgeText(prediction, myTBS);

        const block = document.createElement('div');
        block.id = 'tbsp-profile-block';
        block.style.cssText = `
            margin: 8px 0; padding: 8px 12px;
            background: #1a1a2e; border: 1px solid #333; border-radius: 6px;
            font-size: 13px; color: #eee;
        `;
        block.innerHTML = `
            <span style="color:${color};font-weight:bold;font-size:15px;">[${text}]</span>
            <span style="color:#888;margin-left:8px;font-size:11px;">TBSP prediction</span><br>
            <span style="color:#aaa;font-size:11px;">
                TBS: <b style="color:#eee">${formatTBS(prediction.predicted_tbs)}</b>
                &nbsp;&bull;&nbsp;
                STR: ${formatTBS(prediction.predicted_str || 0)} &nbsp;
                DEF: ${formatTBS(prediction.predicted_def || 0)} &nbsp;
                SPD: ${formatTBS(prediction.predicted_spd || 0)} &nbsp;
                DEX: ${formatTBS(prediction.predicted_dex || 0)}
                <br>Method: ${prediction.method} &bull; Accuracy: ${prediction.confidence}
                &bull; Samples: ${prediction.training_samples}
            </span>
        `;
        anchor.insertAdjacentElement('afterend', block);
    }

    // =========================================================================
    // INJECT — attack page (prominent block near opponent)
    // =========================================================================

    async function injectAttackBadge(targetId) {
        if (NPC_IDS.has(targetId)) return;
        if (document.getElementById('tbsp-attack-block')) return;

        const prediction = await fetchPrediction(targetId);
        if (!prediction) return;

        // The attack page shows opponent on the right side
        const anchor =
            document.querySelector('.right .name') ||
            document.querySelector('[class*="rightPlayer"]') ||
            document.querySelector('[class*="rightSide"]') ||
            document.querySelector('.opponents .right') ||
            document.querySelector('.names-info .right') ||
            document.querySelector('[class*="attackPlayer"]') ||
            document.querySelector('.attack-info');

        const myTBS = getMyTBS();
        const { text, color } = badgeText(prediction, myTBS);

        const block = document.createElement('div');
        block.id = 'tbsp-attack-block';
        block.style.cssText = `
            margin: 6px 0; padding: 6px 10px;
            background: #1a1a2e; border: 1px solid #333; border-radius: 5px;
            font-size: 12px; color: #eee; text-align: center;
        `;
        block.innerHTML = `
            <span style="color:${color};font-weight:bold;font-size:14px;">[${text}]</span>
            <span style="color:#888;font-size:10px;margin-left:6px;">TBSP</span><br>
            <span style="color:#aaa;font-size:10px;">
                TBS: <b style="color:#eee">${formatTBS(prediction.predicted_tbs)}</b>
                &nbsp; STR: ${formatTBS(prediction.predicted_str || 0)}
                &nbsp; SPD: ${formatTBS(prediction.predicted_spd || 0)}
            </span>
        `;

        if (anchor) {
            anchor.insertAdjacentElement('afterend', block);
        } else {
            // No anchor found yet — retry after short delay (attack page loads async)
            setTimeout(() => injectAttackBadge(targetId), 1500);
            return;
        }
    }

    // =========================================================================
    // SCAN — find all player name elements and inject badges
    // =========================================================================

    async function scanAndInject() {
        if (!getToken()) return;

        const pageType = getPageType();

        if (pageType === 'profile') {
            const targetId = getProfileTargetId();
            if (targetId) await injectProfileBadge(targetId);
            return;
        }

        if (pageType === 'attack') {
            const targetId = getAttackTargetId();
            if (targetId) await injectAttackBadge(targetId);
            return;
        }

        // ---- List-type pages ----

        // Primary selector: Torn's standard .user.name class + React variants
        const primary = document.querySelectorAll(
            '.user.name:not([data-tbsp-done]), [class*="userName"]:not([data-tbsp-done]), [class*="user-name"]:not([data-tbsp-done])'
        );
        for (const el of primary) injectBadge(el);

        // Secondary: faction member rows (.t-list li, .members-list li, etc.)
        if (pageType === 'faction') {
            const factionEls = document.querySelectorAll(
                '.members-list .name:not([data-tbsp-done]), [class*="memberItem"] .name:not([data-tbsp-done])'
            );
            for (const el of factionEls) injectBadge(el);
        }

        // Tertiary fallback: any profile link whose parent hasn't been injected yet.
        // This catches HOF tables, competition pages, and any page where .user.name
        // isn't used. We mark each link so we don't re-process it.
        const links = document.querySelectorAll('a[href*="profiles.php?XID="]:not([data-tbsp-link])');
        for (const a of links) {
            a.dataset.tbspLink = '1';
            // Skip if this link's parent container already has a badge
            const container = a.parentElement;
            if (!container || container.querySelector('.tbsp-badge')) continue;
            // Use the link itself as the injection target
            injectBadge(a);
        }
    }

    // =========================================================================
    // MUTATION OBSERVER — Torn is a React SPA
    // =========================================================================

    let _scanTimer = null;
    function scheduleScan() {
        clearTimeout(_scanTimer);
        _scanTimer = setTimeout(scanAndInject, 400);
    }

    const observer = new MutationObserver(mutations => {
        for (const m of mutations) {
            for (const node of m.addedNodes) {
                if (node.nodeType !== 1) continue;
                if (isInChat(node)) continue;
                // Trigger if any meaningful element was added
                if (
                    node.querySelector?.('.user.name') ||
                    node.querySelector?.('a[href*="profiles.php?XID="]') ||
                    node.querySelector?.('a[href*="user2ID="]') ||
                    node.classList?.contains('user') ||
                    /userName|user-name|memberItem/i.test(node.className || '')
                ) {
                    scheduleScan();
                    return; // one trigger per mutation batch is enough
                }
            }
        }
    });

    // =========================================================================
    // SETTINGS UI
    // =========================================================================

    function buildSettingsPanel() {
        const panel = document.createElement('div');
        panel.id = 'tbsp-settings';
        panel.style.cssText = `
            position: fixed; top: 100px; right: 16px; z-index: 99998;
            width: 300px; background: #1a1a2e; border: 1px solid #555;
            border-radius: 8px; padding: 16px; color: #eee; font-size: 13px;
            box-shadow: 0 8px 24px rgba(0,0,0,.7);
        `;

        const token = getToken();
        const myTornId = getMyTornId();

        panel.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <b style="font-size:15px">⚔ TBSP Settings</b>
                <span id="tbsp-close" style="cursor:pointer;font-size:18px;color:#888">✕</span>
            </div>
            ${token ? `
                <div style="color:#73DF5D;margin-bottom:4px">✓ Logged in (ID: ${myTornId})</div>
                <div id="tbsp-sub-info" style="color:#888;font-size:11px;margin-bottom:8px">Checking subscription…</div>
                <button id="tbsp-upload" style="${btnStyle('#2a6496')}">Upload my attacks</button>
                <button id="tbsp-check-pay" style="${btnStyle('#4a3a7a')}">I paid — check subscription</button>
                <button id="tbsp-logout" style="${btnStyle('#6c3a3a')}">Log out</button>
            ` : `
                <div style="margin-bottom:8px">Enter your Torn API key to get started:</div>
                <input id="tbsp-api-key" type="text" placeholder="Torn API key"
                    style="width:100%;box-sizing:border-box;padding:6px 8px;background:#0d0d1a;
                    border:1px solid #555;border-radius:4px;color:#eee;margin-bottom:8px">
                <button id="tbsp-login" style="${btnStyle('#2a6496')}">Connect</button>
                <div style="color:#666;font-size:11px;margin-top:6px">
                    Premium: 1 Xanax / 30 days → our Torn account
                </div>
            `}
            <div id="tbsp-msg" style="margin-top:8px;color:#888;font-size:12px"></div>
            <div style="margin-top:12px;color:#555;font-size:11px">
                My TBS: <span id="tbsp-my-tbs">${getMyTBS() ? formatTBS(getMyTBS()) : 'unknown'}</span>
                &nbsp;&bull;&nbsp;v0.3.4
            </div>
        `;

        document.body.appendChild(panel);

        panel.querySelector('#tbsp-close').onclick = () => panel.remove();

        if (token) {
            // Load subscription status asynchronously
            fetchSubscriptionStatus().then(sub => {
                const el = panel.querySelector('#tbsp-sub-info');
                if (!el) return;
                if (!sub) { el.textContent = 'Subscription: unknown'; return; }
                if (sub.active) {
                    const days = sub.days_remaining != null ? ` (${sub.days_remaining}d left)` : '';
                    el.textContent = `✓ Premium${days}`;
                    el.style.color = '#73DF5D';
                } else {
                    el.textContent = 'No active subscription — send 1 Xanax to get 30 days';
                    el.style.color = '#FFB30F';
                }
            });

            panel.querySelector('#tbsp-logout').onclick = () => {
                ['token','myTbs','myTornId'].forEach(k => S.remove(k));
                panel.remove();
            };
            panel.querySelector('#tbsp-upload').onclick = async () => {
                setMsg('Uploading attacks…');
                const r = await uploadAttacks();
                setMsg(r ? r.message : 'Upload failed');
            };
            panel.querySelector('#tbsp-check-pay').onclick = async () => {
                setMsg('Checking payments…');
                const r = await checkPayments();
                if (!r) { setMsg('Check failed — try again later'); return; }
                setMsg(r.message);
                // Refresh subscription display
                fetchSubscriptionStatus().then(sub => {
                    const el = panel.querySelector('#tbsp-sub-info');
                    if (!el || !sub) return;
                    if (sub.active) {
                        const days = sub.days_remaining != null ? ` (${sub.days_remaining}d left)` : '';
                        el.textContent = `✓ Premium${days}`;
                        el.style.color = '#73DF5D';
                    }
                });
            };
        } else {
            panel.querySelector('#tbsp-login').onclick = async () => {
                const key = panel.querySelector('#tbsp-api-key').value.trim();
                if (!key) return setMsg('Please enter your API key');
                setMsg('Connecting…');
                try {
                    const data = await login(key);
                    setToken(data.token);
                    setMyTornId(data.torn_id);
                    panel.remove();
                    showSettingsButton();
                    await fetchAndStoreMyTBS();
                    scanAndInject();
                    // Fire-and-forget: upload attack logs to grow training data
                    uploadAttacks().then(r => {
                        if (r) S.set('lastUpload', Date.now());
                    }).catch(() => {});
                } catch (e) {
                    setMsg('Error: ' + e.message);
                }
            };
        }

        function setMsg(msg) {
            const el = panel.querySelector('#tbsp-msg');
            if (el) el.textContent = msg;
        }

        return panel;
    }

    function btnStyle(bg) {
        return `width:100%;margin-bottom:6px;padding:7px;background:${bg};color:#eee;
                border:none;border-radius:4px;cursor:pointer;font-size:12px`;
    }

    function showSettingsButton() {
        if (document.getElementById('tbsp-gear')) return;
        const btn = document.createElement('button');
        btn.id = 'tbsp-gear';
        btn.textContent = '⚔ TBSP';
        btn.style.cssText = `
            position: fixed; top: 60px; right: 16px; z-index: 99997;
            padding: 6px 12px; background: #2a6496; color: #eee;
            border: none; border-radius: 20px; cursor: pointer;
            font-size: 12px; font-weight: bold; box-shadow: 0 2px 8px rgba(0,0,0,.5);
        `;
        btn.onclick = () => {
            const existing = document.getElementById('tbsp-settings');
            if (existing) existing.remove(); else buildSettingsPanel();
        };
        document.body.appendChild(btn);
    }

    // =========================================================================
    // STORE OWN TBS
    // =========================================================================

    async function fetchAndStoreMyTBS() {
        try {
            const myId = getMyTornId();
            if (!myId) return;
            const pred = await fetchPrediction(myId);
            if (pred && pred.predicted_tbs) {
                const prev = getMyTBS();
                setMyTBS(pred.predicted_tbs);
                // Re-colour all visible badges if our own TBS value changed
                if (prev !== pred.predicted_tbs) refreshAllBadgeColors();
            }
        } catch {}
    }

    // =========================================================================
    // INIT
    // =========================================================================

    function init() {
        showSettingsButton();

        observer.observe(document.body, { childList: true, subtree: true });

        // Initial scan
        scheduleScan();

        // Auto-upload attacks once per day
        const lastUpload = S.get('lastUpload', 0);
        if (getToken() && Date.now() - lastUpload > 24 * 60 * 60 * 1000) {
            uploadAttacks().then(r => {
                if (r) { S.set('lastUpload', Date.now()); }
            });
        }
    }

    if (document.body) {
        init();
    } else {
        document.addEventListener('DOMContentLoaded', init);
    }

})();
