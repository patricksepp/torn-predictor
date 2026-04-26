# Torn Battle Stats Predictor (TBSP)

## Projekti ülevaade
Avalik Tampermonkey userscript + backend server Torn.com mängijatele.
Ennustab mängijate lahingustatsid (str/def/spd/dex) masinõppe abil.
Sarnane olemasoleva BSP skriptiga (lol-manager.com) aga HTTPS, avatud ja tasuta/premium mudel.

## Monetiseerimine
- **Tasuta tier**: ennustused rank-põhiselt (kohe saadaval, 0 spy andmeid vaja)
- **Premium tier**: täpsemad ML ennustused rünnakulogide põhjal
- Makse: 1 xanax / 30 päeva (saadetakse meie Torn kontole, automaatne kontroll)
- 1 nädal tasuta uutele kasutajatele

## Stack
- **Backend**: Python 3.11 + FastAPI — Railway hosting
- **DB**: Supabase (PostgreSQL)
- **ML**: scikit-learn + XGBoost
- **Admin dashboard**: Next.js — Vercel hosting (vercel.com, tasuta, push GitHubist → live)
- **Kasutajale**: Tampermonkey userscript (.user.js)

---

## Torn API info

### API võtme tüübid
- `Limited Access` — minimaalne mida vajame
- `Full Access` / `Custom` — parim kogemus

### Torn API endpointid mida kasutame

**Mängija profiil (ML features):**
```
GET https://api.torn.com/user/{id}?selections=profile,personalstats&key={apikey}
```
Vastus:
```json
{
  "player_id": 123456,
  "name": "PlayerName",
  "level": 85,
  "rank": "Idolized",
  "donordays": 365,
  "age": 4200,
  "personalstats": {
    "xantaken": 1250,
    "energydrinkused": 890,
    "gymstrength": 3400,
    "gymspeed": 2100,
    "gymdefense": 2800,
    "gymdexterity": 1900,
    "attackswon": 2340,
    "attackslost": 123,
    "defendswon": 456,
    "defendslost": 89,
    "statenhancersused": 340,
    "refills": 1200,
    "nerverefills": 450
  }
}
```

**Rünnakulogid (treeningandmed):**
```
GET https://api.torn.com/user/?selections=attacks&key={apikey}
```
Vastus:
```json
{
  "attacks": {
    "123456": {
      "attacker_id": 111,
      "defender_id": 222,
      "result": "Hospitalized",
      "modifiers": { "fair_fight": 1.23 },
      "timestamp_started": 1700000000
    }
  }
}
```

**Fair fight valem — KRIITILINE treeningandmete allikas:**
```
fair_fight = sqrt(attacker_total_stats) / sqrt(defender_total_stats)
Seega: defender_tbs = (sqrt(attacker_tbs) / fair_fight) ^ 2
```
Kui teame ründaja statsid → saame arvutada kaitsja statsid igast rünnakust!

**Stat rank → TBS vahemikud:**
```
"Absolute beginner" → 0 - 2,000
"Beginner"          → 2,000 - 10,000
"Intermediate"      → 10,000 - 25,000
"Experienced"       → 25,000 - 75,000
"Veteran"           → 75,000 - 200,000
"Distinguished"     → 200,000 - 2,000,000
"Highly regarded"   → 2,000,000 - 10,000,000
"Idolized"          → 10,000,000 - 50,000,000
"Champion"          → 50,000,000 - 100,000,000
"Heroic"            → 100,000,000 - 200,000,000
"Legendary"         → 200,000,000+
```

### Torn API vea koodid mida peame käsitlema
```
13 → Kasutaja pole 7 päeva aktiivne → märgi api_key_status='inactive', ÄRA kustuta
16 → Access level liiga madal → teavita kasutajat
18 → Võti on pausitatud → märgi api_key_status='paused', ÄRA kustuta
```

### Rate limits
- Max 100 päringut/minutis per võti
- Server kasutab kasutaja enda võtit (ei koorma meie serverit)

---

## Kasutaja identiteet ja API võtme haldus

**KRIITILINE DISAINIOTSUS: kasutaja identiteet = torn_id, MITTE api_key**

Kasutaja võib API võtit vahetada nii mitu korda kui tahab.
torn_id on püsiv identiteet — see ei muutu kunagi.

### Login/register voog
```python
async def login_or_register(api_key: str) -> dict:
    # 1. Päri Torn API-st kes see on
    data = await fetch_torn_basic(api_key)
    torn_id = data['player_id']
    torn_name = data['name']

    # 2. Otsi Supabase'ist torn_id järgi (MITTE api_key järgi!)
    user = await db.get_user_by_torn_id(torn_id)

    if user:
        # Kasutaja olemas → uuenda API võti (võib olla muutunud)
        await db.update_api_key(torn_id, encrypt(api_key))
        await db.update_last_seen(torn_id)
    else:
        # Uus kasutaja → loo konto
        await db.create_user(torn_id, torn_name, encrypt(api_key))
        await db.grant_free_week(torn_id)

    # 3. Tagasta JWT (identiteet = torn_id)
    return create_jwt(torn_id=torn_id, torn_name=torn_name)
```

### API võtme staatused
```python
# api_key_status väli users tabelis:
'active'    # töötab normaalselt
'paused'    # kasutaja pausitas Tornis (error 18) — konto alles
'inactive'  # kasutaja pole 7 päeva aktiivne (error 13) — konto alles
'invalid'   # võti kustutatud — küsi uut
```

### Konto kustutamine (GDPR)
```python
async def delete_user_data(torn_id: int):
    # Kustuta isiklikud andmed
    await db.delete_user(torn_id)           # kasutaja rida
    await db.delete_predictions(torn_id)    # ennustuste cache
    # Anonümiseeri treeningandmed (ÄRA kustuta — need on väärtuslikud)
    await db.anonymize_training_data(torn_id)  # contributed_by → NULL
```

---

## Torn API access level juhend kasutajale

### Minimaalne (Limited Access)
```
user → basic, profile, personalstats, attacks
```
- ✅ Rank-põhine ennustus, rünnakulogid, värviline badge
- ❌ Enda täpseid statsid ei tea → värvid vähem täpsed

### Soovitatav (Custom)
```
user → basic, profile, personalstats, attacks, battlestats
```
- ✅ Kõik eelnev + täpsed enda statsid + paremad treeningandmed

### Mida me EI vaja ega küsi
```
❌ items, money, networth, messages, mail, faction management
```

### Võtme valideerimine
```python
async def validate_api_key(api_key: str) -> dict:
    data = await fetch("https://api.torn.com/user/?selections=basic,profile&key=" + api_key)
    key_info = await fetch("https://api.torn.com/key/?selections=info&key=" + api_key)
    # access_level: 1=Public, 2=Minimal, 3=Limited, 4=Full, 10=Custom
    return {
        "torn_id": data['player_id'],
        "name": data['name'],
        "access_level": key_info['access_level'],
        "has_attacks": key_info['access_level'] >= 3,
        "has_battlestats": key_info['access_level'] >= 4,
    }
```

---

## ML Pipeline

### Faas 1: Rank-põhine ennustus (kohe kasutatav, 0 treeningandmeid)
```python
RANK_RANGES = {
    "Absolute beginner": (0, 2_000),
    "Beginner": (2_000, 10_000),
    "Intermediate": (10_000, 25_000),
    "Experienced": (25_000, 75_000),
    "Veteran": (75_000, 200_000),
    "Distinguished": (200_000, 2_000_000),
    "Highly regarded": (2_000_000, 10_000_000),
    "Idolized": (10_000_000, 50_000_000),
    "Champion": (50_000_000, 100_000_000),
    "Heroic": (100_000_000, 200_000_000),
    "Legendary": (200_000_000, 500_000_000),
}

def rank_predict(rank: str, level: int) -> dict:
    low, high = RANK_RANGES.get(rank, (0, 10_000))
    level_factor = min(level / 100, 1.0)
    predicted_tbs = low + (high - low) * (0.3 + 0.7 * level_factor)
    return {"predicted_tbs": int(predicted_tbs), "confidence": "low", "method": "rank"}
```

### Faas 2: XGBoost mudel rünnakulogidest

**ML features (X):**
```python
features = [
    'level', 'donordays', 'age_days',
    'xantaken', 'energydrinkused',
    'gymstrength', 'gymspeed', 'gymdefense', 'gymdexterity',
    'attackswon', 'statenhancersused', 'refills', 'nerverefills'
]
```
**Target (Y):** `log(str + def + spd + dex)` — log transform parema mudeli jaoks

```python
from xgboost import XGBRegressor
import numpy as np

model = XGBRegressor(n_estimators=500, max_depth=6, learning_rate=0.05,
                     subsample=0.8, colsample_bytree=0.8, random_state=42)
y_train = np.log1p(tbs_values)
model.fit(X_train, y_train)
# Ennustamisel: predicted_tbs = np.expm1(model.predict(X_new))
```
**Eesmärk:** MAPE < 30%

### Faas 3: Hübriid (automaatne)
```python
def predict(target_id, requester_api_key):
    cached = get_cache(target_id)
    if cached: return cached

    profile = fetch_torn_profile(target_id, requester_api_key)

    if ml_model_ready():  # > 100 treeningpunkti
        result = ml_predict(profile)
        result['method'] = 'ml'
    else:
        result = rank_predict(profile['rank'], profile['level'])
        result['method'] = 'rank'

    save_cache(target_id, result, expires_days=5)
    return result
```

---

## Badge display loogika (3 faasi)

### Faas 1 — ainult rank (< 100 treeningpunkti)
```
[●] Strong
```

### Faas 2 — ligikaudne number (100–500 treeningpunkti)
```
[●] Strong ~28M
```

### Faas 3 — täpne ML ennustus (500+ treeningpunkti)
```
[●] Strong 28.4M
```

### Badge + tooltip kood
```javascript
const COLOR_THRESHOLDS = [
    { maxPercent: 5,        color: '#949494', label: 'Very Weak' },
    { maxPercent: 35,       color: '#FFFFFF', label: 'Weak' },
    { maxPercent: 75,       color: '#73DF5D', label: 'Moderate' },
    { maxPercent: 125,      color: '#47A6FF', label: 'Strong' },
    { maxPercent: 400,      color: '#FFB30F', label: 'Very Strong' },
    { maxPercent: Infinity, color: '#FF0000', label: 'Dangerous' },
];

function formatTBS(tbs) {
    if (tbs >= 1_000_000_000) return `${(tbs/1e9).toFixed(1)}B`;
    if (tbs >= 1_000_000)     return `${(tbs/1e6).toFixed(1)}M`;
    if (tbs >= 1_000)         return `${(tbs/1e3).toFixed(0)}K`;
    return String(tbs);
}

function getColor(targetTBS, myTBS) {
    const percent = (targetTBS / myTBS) * 100;
    return COLOR_THRESHOLDS.find(t => percent <= t.maxPercent);
}

function formatBadgeText(predicted_tbs, method, training_samples, user_tbs) {
    const { color, label } = getColor(predicted_tbs, user_tbs);
    const readable = formatTBS(predicted_tbs);
    let text;
    if (method === 'rank' || training_samples < 100) text = label;
    else if (training_samples < 500) text = `${label} ~${readable}`;
    else text = `${label} ${readable}`;
    return { text, color };
}

function createTooltip(prediction) {
    // Hover peale näitab:
    // TBS, STR, DEF, SPD, DEX ligikaudsed väärtused
    // Meetod (rank / ML / spy)
    // Täpsus (madal / keskmine / kõrge)
    // Viimati uuendatud (X päeva tagasi)
}
```

---

## Supabase DB skeem

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    torn_id INTEGER UNIQUE NOT NULL,          -- IDENTITEET, ei muutu
    torn_name TEXT,
    torn_api_key_encrypted TEXT NOT NULL,     -- uuendatakse kui võti muutub
    api_key_status TEXT DEFAULT 'active',     -- active/paused/inactive/invalid
    role TEXT DEFAULT 'user',                 -- user/moderator/admin
    subscription_tier TEXT DEFAULT 'free',
    subscription_end TIMESTAMPTZ,
    own_tbs BIGINT,
    own_str BIGINT, own_def BIGINT,
    own_spd BIGINT, own_dex BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE training_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    torn_id INTEGER NOT NULL,
    estimated_tbs BIGINT NOT NULL,
    source_attack_id TEXT,
    level INTEGER, donordays INTEGER, age_days INTEGER,
    xantaken INTEGER, energydrinkused INTEGER,
    gymstrength INTEGER, gymspeed INTEGER,
    gymdefense INTEGER, gymdexterity INTEGER,
    attackswon INTEGER, statenhancersused INTEGER,
    refills INTEGER, nerverefills INTEGER,
    contributed_by INTEGER,   -- NULL kui kasutaja kustutab konto (anonümiseeritud)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE predictions_cache (
    torn_id INTEGER PRIMARY KEY,
    predicted_tbs BIGINT NOT NULL,
    predicted_str BIGINT, predicted_def BIGINT,
    predicted_spd BIGINT, predicted_dex BIGINT,
    confidence TEXT,   -- low/medium/high
    method TEXT,       -- rank/ml/spy
    model_version TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE model_versions (
    version TEXT PRIMARY KEY,
    training_samples INTEGER,
    rmse FLOAT, mape FLOAT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    torn_id INTEGER NOT NULL,
    xanax_trade_id TEXT UNIQUE,
    days_granted INTEGER DEFAULT 30,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_torn_id INTEGER NOT NULL,
    action TEXT NOT NULL,        -- 'role_change', 'ban', 'subscription_edit' jne
    target_torn_id INTEGER,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_training_torn_id ON training_data(torn_id);
CREATE INDEX idx_cache_expires ON predictions_cache(expires_at);
CREATE INDEX idx_users_torn_id ON users(torn_id);

-- Esimene admin (käivita Supabase SQL editoris oma torn_id-ga):
-- UPDATE users SET role = 'admin' WHERE torn_id = SINU_TORN_ID;
```

---

## FastAPI endpointid

```
POST /api/auth/login              → API võti → torn_id otsing → JWT
GET  /api/predict/{target_id}     → ennustus (rank või ML)
POST /api/data/upload-attacks     → rünnakulogide töötlus
GET  /api/subscription/status     → subscriptsioon info
GET  /api/health                  → server status

# Admin endpointid (nõuavad role=admin või role=moderator)
GET  /api/admin/users             → kõik kasutajad (moderator+)
GET  /api/admin/users/{torn_id}   → ühe kasutaja detail (moderator+)
PUT  /api/admin/users/{torn_id}/role      → muuda rolli (ainult admin)
PUT  /api/admin/users/{torn_id}/subscription → muuda sub käsitsi (ainult admin)
DELETE /api/admin/users/{torn_id} → kustuta kasutaja GDPR (ainult admin)
GET  /api/admin/ml/stats          → mudeli statistika (moderator+)
POST /api/admin/ml/train          → käivita uus treenimine (ainult admin)
GET  /api/admin/payments          → maksete logi (moderator+)
GET  /api/admin/stats/overview    → dashboard numbrid (moderator+)
```

---

## Admin dashboard (Next.js → Vercel)

### Sisselogimine
Torn API võtmega — sama loogika mis userscriptil:
```
1. Admin sisestab Torn API võtme
2. Backend valideerib → tagastab JWT
3. Frontend kontrollib: role === 'admin' || role === 'moderator'
4. Kui ei ole → "Access denied"
```

Esimene admin luuakse käsitsi Supabase SQL editoris:
```sql
UPDATE users SET role = 'admin' WHERE torn_id = SINU_TORN_ID;
```

### Dashboard lehed

**📊 Overview** (moderator+):
- Kasutajaid kokku / aktiivseid täna / selle nädal
- Ennustusi täna / selle nädal
- Treeningandmeid kokku
- Mudeli MAPE % trend (graafik)
- Viimased 10 liitujat

**👥 Kasutajad** (moderator+):
- Tabel: Torn nimi (link profiilile), ID, tase, liitumine, viimati aktiivne
- Subscriptsioon: tier + lõppkuupäev + staatus
- Andmete panus: mitu rünnakulogi saadetud
- API võtme staatus: active/paused/inactive/invalid
- Roll: user/moderator/admin
- Admin saab muuta: rolli, subscriptsioon, keelata konto

**🔑 Rollide haldus** (ainult admin):
- Muuda kasutaja rolli (user ↔ moderator ↔ admin)
- Kõik muutused logitakse admin_audit_log tabelisse
- Moderaatorid näevad kõike aga ei saa midagi muuta

**🤖 ML monitor** (moderator+):
- Treeningandmete arv ajas (graafik)
- Mudeli täpsus (MAPE %) versiooni kaupa
- Viimane treenimine millal + kui kaua kestis
- "Treeni uus mudel" nupp (ainult admin)
- Andmete jaotus: kes on panustanud mitu rünnakulogi

**💰 Maksed** (moderator+):
- Xanax maksete logi: kes, millal, mitu päeva lisati
- Käsitsi subscriptsioon lisamine/eemaldamine (ainult admin)

**⚙️ Seaded** (ainult admin):
- Teade kõigile kasutajatele (kuvatakse userscriptis bannerina)
- Globaalne maintenance mode (lülitab ennustused välja)

### Rollide õigused kokkuvõte
```
                    admin    moderator
Näha kasutajaid:     ✅         ✅
Näha ML statsi:      ✅         ✅
Näha makseid:        ✅         ✅
Muuta rolle:         ✅         ❌
Muuta subscriptsioon:✅         ❌
Kustutada kasutajaid:✅         ❌
Käivitada ML treeni: ✅         ❌
Süsteemi seaded:     ✅         ❌
```

---

## Projekti struktuur

```
torn-predictor/
├── CLAUDE.md
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── predict.py
│   │   ├── data.py
│   │   ├── subscription.py
│   │   └── admin.py
│   ├── services/
│   │   ├── torn_api.py
│   │   ├── predictor.py
│   │   ├── training.py
│   │   └── payments.py
│   ├── ml/
│   │   ├── train.py
│   │   ├── features.py
│   │   ├── rank_predictor.py
│   │   └── models/
│   ├── db/
│   │   ├── supabase_client.py
│   │   └── schema.sql
│   ├── utils/
│   │   ├── crypto.py
│   │   └── jwt.py
│   ├── config.py
│   ├── requirements.txt
│   └── .env
├── admin-dashboard/          # Next.js → Vercel
│   ├── pages/
│   │   ├── index.tsx         # Login
│   │   ├── overview.tsx
│   │   ├── users.tsx
│   │   ├── ml.tsx
│   │   └── payments.tsx
│   ├── components/
│   └── package.json
├── userscript/
│   └── torn_predictor.user.js
├── .gitignore
└── railway.toml
```

---

## Environment muutujad (.env)

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
JWT_SECRET=random-64-char-string
FERNET_KEY=...
OUR_TORN_API_KEY=...
OUR_TORN_ID=...
PORT=8000
ENVIRONMENT=development
```

---

## Userscript inject lehed

```javascript
// @match  https://www.torn.com/profiles.php*
// @match  https://www.torn.com/factions.php*
// @match  https://www.torn.com/halloffame.php*
// @match  https://www.torn.com/index.php?page=people*
// @match  https://www.torn.com/bounties.php*
// @match  https://www.torn.com/hospitalview.php*
// @match  https://www.torn.com/forums.php*
// @match  https://www.torn.com/page.php*
// @match  https://www.torn.com/joblist.php*
// @match  https://www.torn.com/competition.php*
// @match  https://www.torn.com/pmarket.php*
// @match  https://www.torn.com/properties.php*
// @match  https://www.torn.com/war.php*
// @match  https://www.torn.com/loader.php?sid=attack*
// @match  https://www.torn.com/page.php?sid=list&type=friends
// @match  https://www.torn.com/page.php?sid=list&type=enemies
// @match  https://www.torn.com/page.php?sid=list&type=targets
```

### Userscripti cache loogika
```javascript
async function getPrediction(targetId) {
    const cacheKey = `tbsp_${targetId}`;
    const cached = JSON.parse(localStorage.getItem(cacheKey) || 'null');
    if (cached && Date.now() < cached.expires) return cached;

    const response = await fetch(`${TBSP_SERVER}/api/predict/${targetId}`, {
        headers: { 'Authorization': `Bearer ${getUserToken()}` }
    });
    const data = await response.json();
    localStorage.setItem(cacheKey, JSON.stringify({
        ...data,
        expires: Date.now() + 5 * 24 * 60 * 60 * 1000
    }));
    return data;
}
```

---

## Järgmised sammud (järjekorras)

- [ ] **Samm 1**: Projekti struktuur + `python -m venv venv` + requirements install
- [ ] **Samm 2**: `.env` fail + Supabase projekt loomine (supabase.com)
- [ ] **Samm 3**: `schema.sql` käivitamine Supabase SQL editoris
- [ ] **Samm 4**: Torn API ühenduse test (`torn_api.py`)
- [ ] **Samm 5**: Rank-põhine ennustus (`rank_predictor.py`)
- [ ] **Samm 6**: FastAPI auth endpoint (`/api/auth/login`) — torn_id põhine
- [ ] **Samm 7**: FastAPI predict endpoint (`/api/predict/{id}`)
- [ ] **Samm 8**: Rünnakulogide töötlus treeningandmeteks (`training.py`)
- [ ] **Samm 9**: XGBoost mudeli treenimine (`train.py`)
- [ ] **Samm 10**: Userscript põhistruktuur (inject + badge + tooltip)
- [ ] **Samm 11**: Userscript kõikidel lehtedel
- [ ] **Samm 12**: Premium/subscriptsioon süsteem + xanax makse kontroll
- [ ] **Samm 13**: Admin dashboard (Next.js) — login + overview + kasutajad
- [ ] **Samm 14**: Admin rollide haldus + audit log
- [ ] **Samm 15**: Railway deploy (backend) + Vercel deploy (admin dashboard)

## NB! Alusta alati Sammust 1 kui pole tehtud, muidu jätka sealt kus pooleli jäi.
