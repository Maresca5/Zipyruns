# ⚡ PaceForge — Race Predictor & Training Analytics

Darmowa alternatywa dla Strava Premium Fitness Intelligence.  
Łączy się z Twoim kontem Strava przez OAuth i daje Ci:

- 📈 **Prognozy czasów** na 5 dystansach (VDOT / Riegel)
- 🗺️ **Race Strategy** — pacing plan km po km z 4 strategiami
- 🫀 **Strefy treningowe** — Daniels (tempo) + Karvonen (HR)
- 📊 **Progresja VDOT** w czasie + trend miesięczny
- 🏆 **Najlepsze wyniki** na każdym dystansie
- ❤️ **Aerobic fitness** — HR efficiency, HR vs pace scatter
- 😮‍💨 **Forma i zmęczenie** — model ATL/CTL/TSB (Banister)

---

## 🚀 Szybki start (3 kroki)

### Krok 1 — Utwórz aplikację Strava

1. Wejdź na **https://www.strava.com/settings/api**
2. Wypełnij formularz:
   - **Application Name:** PaceForge (lub cokolwiek)
   - **Category:** Data Analysis
   - **Club:** (zostaw puste)
   - **Website:** `https://paceforge.streamlit.app` *(Twój przyszły URL)*
   - **Authorization Callback Domain:** `paceforge.streamlit.app` *(bez https://)*
3. Kliknij **Create** → pojawią się:
   - `Client ID` — numer ~6 cyfr
   - `Client Secret` — długi hash

> ⚠️ **Callback Domain** musisz zaktualizować po deploymencie na Streamlit Cloud.

---

### Krok 2 — Przygotuj repo na GitHub

```bash
# Sklonuj / zforkuj to repo
git clone https://github.com/TWOJ_USERNAME/paceforge.git
cd paceforge

# Utwórz lokalny plik secrets (NIE commituj!)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edytuj `.streamlit/secrets.toml`:
```toml
STRAVA_CLIENT_ID     = "123456"          # ← Twój Client ID
STRAVA_CLIENT_SECRET = "abc123..."       # ← Twój Client Secret
STRAVA_REDIRECT_URI  = "http://localhost:8501"   # ← na razie localhost
```

Sprawdź lokalnie:
```bash
pip install -r requirements.txt
streamlit run app.py
```

---

### Krok 3 — Deploy na Streamlit Cloud

1. Wejdź na **https://share.streamlit.io**
2. Kliknij **New app** → wybierz swoje repo → main branch → `app.py`
3. Kliknij **Advanced settings** → **Secrets** i wklej:
   ```toml
   STRAVA_CLIENT_ID     = "123456"
   STRAVA_CLIENT_SECRET = "abc123..."
   STRAVA_REDIRECT_URI  = "https://TWOJA-APPKA.streamlit.app"
   ```
4. Kliknij **Deploy** — za ~2 minuty masz URL
5. **Wróć do Strava API settings** i zaktualizuj:
   - Website: `https://TWOJA-APPKA.streamlit.app`
   - Authorization Callback Domain: `TWOJA-APPKA.streamlit.app`

---

## 🏗️ Struktura projektu

```
paceforge/
├── app.py                    # Główna aplikacja, routing, OAuth
├── requirements.txt
├── .gitignore
├── .streamlit/
│   ├── config.toml           # Dark theme
│   ├── secrets.toml          # ← lokalnie (NIE commituj!)
│   └── secrets.toml.example  # Szablon
├── utils/
│   ├── strava.py             # Strava API, VDOT, Riegel, strefy
│   └── session.py            # Stan sesji, ATL/CTL/TSB, TRIMP
└── pages/
    ├── dashboard.py          # Przegląd + CTL/ATL wykres
    ├── predictions.py        # Prognozy czasów
    ├── strategy.py           # Race strategy km/km
    ├── history.py            # Analiza historyczna (4 taby)
    └── zones.py              # Strefy tempa i HR
```

---

## 🧮 Algorytmy

### VDOT (Jack Daniels Running Formula)
```
VO₂ = -4.60 + 0.182258·v + 0.000104·v²        (v = prędkość m/min)
%VO₂max = 0.8 + 0.1894·e^(-0.01278·t) + 0.2990·e^(-0.1933·t)
VDOT = VO₂ / %VO₂max
```
Używany do: prognoz, stref tempa, monitoringu formy.

### Riegel's Formula
```
T₂ = T₁ × (D₂/D₁)^1.06
```
Alternatywna prognoza — uśredniana z Danielsem.

### Karvonen (strefy HR)
```
HR_target = HR_rest + %HRR × (HR_max - HR_rest)
```

### TRIMP + ATL/CTL/TSB (Banister)
```
TRIMP = czas[min] × HRR_frac × 0.64 × e^(1.92 × HRR_frac)
CTL   = CTL_prev + (TRIMP - CTL_prev) × (2/43)   # τ = 42 dni
ATL   = ATL_prev + (TRIMP - ATL_prev) × (2/8)    # τ =  7 dni
TSB   = CTL - ATL                                  # Form
```

---

## 🔒 Prywatność

- Aplikacja prosi **wyłącznie** o scope `read` + `activity:read_all`
- Żadne dane nie są zapisywane na serwerze — wszystko w sesji Streamlit
- Token OAuth wygasa po 6h (auto-refresh działa w tle)
- Możesz odwołać dostęp w dowolnej chwili: **Strava → Settings → My Apps**

---

## 🛠️ Dalszy rozwój (TODO)

- [ ] Garmin Connect integration (gdy API stanie się dostępne)
- [ ] Export planu treningowego do CSV/iCal
- [ ] Powiadomienia Telegram o formie (integracja z istniejącym botem?)
- [ ] Analiza elevation gain i trail runs
- [ ] Porównanie z innymi atletami (anonimowe benchmarki)

---

## 📝 Licencja

MIT — rób co chcesz.
