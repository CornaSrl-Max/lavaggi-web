# -*- coding: utf-8 -*-
"""
FV Wash Manager Platinum+ - Versione Portale Web
Backend: Google Sheets
Frontend: Streamlit, utilizzabile anche dentro Google Sites tramite embed/link.

Requisiti:
    pip install streamlit pandas gspread google-auth

Secrets richiesti in .streamlit/secrets.toml:
    [gcp_service_account]
    ... credenziali service account ...

    [google_sheet]
    spreadsheet_id = "ID_DEL_GOOGLE_SHEET"
    worksheet_name = "Lavaggi"   # opzionale, default Lavaggi
"""

import html
import json
import re
import urllib.parse
from datetime import date, datetime
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ==========================================================
# 1. CONFIGURAZIONE BASE
# ==========================================================
st.set_page_config(
    page_title="FV Wash Manager Platinum+",
    layout="wide",
    page_icon="FV",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
FILE_MODELLI = BASE_DIR / "modelli_messaggi.json"

SHEET_ID = "16RUw8kcZRurs_LYP9WCGbbLiXZnHEhw_lLEsdlS5Zuc"
FOGLIO = st.secrets.get("google_sheet", {}).get("worksheet_name", "Lavaggi")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit" if SHEET_ID else ""

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ==========================================================
# 2. STILE GRAFICO PORTALE
# ==========================================================
st.markdown(
    """
<style>
:root{
    --bg:#f4f7fb;
    --panel:#ffffff;
    --nav:#0b1f35;
    --nav2:#102d4a;
    --blue:#2563eb;
    --green:#16a34a;
    --orange:#f59e0b;
    --red:#dc2626;
    --purple:#7c3aed;
    --muted:#64748b;
    --text:#0f172a;
    --line:#e2e8f0;
}
.stApp { background: var(--bg); color: var(--text); }
[data-testid="stHeader"] { background: rgba(244,247,251,.88); backdrop-filter: blur(12px); }
[data-testid="stSidebar"] { background: linear-gradient(180deg, var(--nav), var(--nav2)); }
[data-testid="stSidebar"] * { color: #f8fafc !important; }
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1520px; }
.main-title { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1.2rem; }
.title-left h1 { font-size:2.05rem; line-height:1.1; font-weight:950; margin:0; color:var(--text); }
.title-left p { margin:.35rem 0 0 0; color:var(--muted); font-size:.95rem; }
.card { background:var(--panel); border:1px solid var(--line); border-radius:22px; padding:18px; box-shadow:0 10px 26px rgba(15,23,42,.055); }
.kpi-card { background:var(--panel); border:1px solid var(--line); border-radius:22px; padding:16px; min-height:120px; box-shadow:0 10px 24px rgba(15,23,42,.055); }
.kpi-row { display:flex; align-items:center; gap:13px; }
.kpi-icon { width:58px; height:58px; display:flex; align-items:center; justify-content:center; border-radius:20px; font-size:30px; flex-shrink:0; box-shadow: inset -7px -8px 18px rgba(15,23,42,.10), inset 7px 7px 18px rgba(255,255,255,.65); }
.kpi-blue{background:linear-gradient(145deg,#dbeafe,#60a5fa)}
.kpi-green{background:linear-gradient(145deg,#dcfce7,#22c55e)}
.kpi-red{background:linear-gradient(145deg,#fee2e2,#f97316)}
.kpi-purple{background:linear-gradient(145deg,#ede9fe,#8b5cf6)}
.kpi-slate{background:linear-gradient(145deg,#f1f5f9,#64748b)}
.kpi-label{color:var(--muted);font-size:.84rem;font-weight:800;margin:0;}
.kpi-value{color:var(--text);font-size:1.85rem;font-weight:950;margin:2px 0 0 0;}
.kpi-hint{color:var(--muted);font-size:.78rem;margin:.5rem 0 0 0;}
.section-title{font-size:1.08rem;font-weight:950;margin:0 0 14px 0;color:var(--text);}
.iconless-title{display:flex;align-items:center;gap:12px;}
.iconless-title:before{content:"";width:10px;height:28px;border-radius:999px;background:#2563eb;display:inline-block;}
.badge{display:inline-flex;align-items:center;border-radius:999px;padding:5px 10px;font-size:.75rem;font-weight:900;border:1px solid transparent;}
.badge-green{background:#dcfce7;color:#166534;border-color:#bbf7d0;}
.badge-blue{background:#dbeafe;color:#1d4ed8;border-color:#bfdbfe;}
.badge-orange{background:#ffedd5;color:#c2410c;border-color:#fed7aa;}
.badge-red{background:#fee2e2;color:#b91c1c;border-color:#fecaca;}
.badge-gray{background:#f1f5f9;color:#475569;border-color:#e2e8f0;}
.badge-purple{background:#ede9fe;color:#6d28d9;border-color:#ddd6fe;}
.detail-box{background:#f8fafc;border:1px solid var(--line);border-radius:16px;padding:13px;min-height:70px;}
.detail-label{color:var(--muted);font-size:.78rem;font-weight:850;margin-bottom:4px;}
.detail-value{color:var(--text);font-size:.95rem;font-weight:850;overflow-wrap:anywhere;}
.urgent-box{background:#fee2e2;color:#991b1b;border:1px solid #fecaca;border-radius:16px;padding:12px 14px;font-weight:900;margin-bottom:14px;}
.ok-box{background:#dcfce7;color:#166534;border:1px solid #bbf7d0;border-radius:16px;padding:12px 14px;font-weight:900;margin-bottom:14px;}
.small-muted{color:var(--muted);font-size:.82rem;}
.stButton>button { border-radius:14px !important; font-weight:900 !important; min-height:42px; white-space:pre-line !important; }
button[kind="secondary"] { background:#ffffff !important; border:1px solid #e2e8f0 !important; color:#0f172a !important; }
button[kind="secondary"]:hover { border-color:#2563eb !important; background:#eff6ff !important; color:#0f172a !important; }
.stDownloadButton>button { border-radius:14px !important; font-weight:900 !important; min-height:42px; }
input, textarea, div[data-baseweb="select"] span { color: var(--text) !important; }
label, .stTextInput label p, .stSelectbox label p, .stTextArea label p { color: var(--text) !important; font-weight:800 !important; }
.sidebar-logo-3d{width:58px;height:58px;border-radius:20px;background:radial-gradient(circle at 34% 26%, #fff 0 10%, #93c5fd 12% 28%, #2563eb 48%, #0b1f35 100%);box-shadow:inset -8px -10px 20px rgba(15,23,42,.35), inset 8px 8px 18px rgba(255,255,255,.5), 0 16px 30px rgba(37,99,235,.25);margin-bottom:12px;}
.author-mark{position:fixed;left:18px;bottom:10px;z-index:9999;font-size:10px;letter-spacing:1.8px;color:rgba(248,250,252,.55)!important;font-weight:800;}
.portal-note{font-size:.8rem;color:#94a3b8!important;line-height:1.35;margin-top:10px;}
a.clean-link {text-decoration:none!important;}
.link-button{display:block;text-align:center;border-radius:14px;padding:11px 14px;font-weight:900;text-decoration:none!important;border:1px solid #ddd6fe;background:#ede9fe;color:#6d28d9!important;}
.link-button-green{display:block;text-align:center;border-radius:14px;padding:11px 14px;font-weight:900;text-decoration:none!important;border:1px solid #bbf7d0;background:#dcfce7;color:#166534!important;}
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# 3. GOOGLE SHEETS
# ==========================================================
@st.cache_resource(show_spinner=False)
def get_worksheet():
    if not SHEET_ID:
        st.error("Manca spreadsheet_id nel file .streamlit/secrets.toml")
        st.stop()

    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )
    client = gspread.authorize(creds)
    sh = client.open_by_key(SHEET_ID)

    try:
        return sh.worksheet(FOGLIO)
    except gspread.WorksheetNotFound:
        tabs = [w.title for w in sh.worksheets()]
        st.error(f"Foglio '{FOGLIO}' non trovato. Schede disponibili: {', '.join(tabs)}")
        st.stop()

# ==========================================================
# 4. FUNZIONI CORE
# ==========================================================
def carica_modelli():
    modelli_base = {
        "fornitori": ["BG Service (commerciale@bgservicebergamo.com)"],
        "mail_30_ogg": "Programmazione lavaggio FV - [CLIENTE] - [DATA]",
        "mail_30_txt": "Gentile cliente,\n\nVi informiamo che abbiamo programmato il lavaggio dell'impianto [IMPIANTO] per il giorno [DATA] [ORARIO].\n\nCordiali saluti",
        "mail_3_ogg": "Promemoria lavaggio FV - [CLIENTE] - [DATA]",
        "mail_3_txt": "Gentile cliente,\n\nvi ricordiamo l'appuntamento per il lavaggio dell'impianto [IMPIANTO] previsto il giorno [DATA] [ORARIO].\n\nCordiali saluti",
        "wa_30_txt": "Gentile cliente, abbiamo programmato il lavaggio dell'impianto FV per il giorno *[DATA] [ORARIO]*.",
        "wa_3_txt": "Gentile cliente, promemoria lavaggio impianto FV previsto il giorno *[DATA] [ORARIO]*.",
        "mail_forn_ogg": "Conferma intervento lavaggio FV - [CLIENTE] - [DATA]",
        "mail_forn_txt": "Buongiorno,\n\nconfermiamo intervento di lavaggio FV per [CLIENTE] il giorno [DATA] [ORARIO].\nImpianto: [IMPIANTO].\n\nCordiali saluti",
    }
    if FILE_MODELLI.exists():
        try:
            with open(FILE_MODELLI, "r", encoding="utf-8") as f:
                modelli_base.update(json.load(f))
        except Exception:
            pass
    return modelli_base

if "modelli" not in st.session_state:
    st.session_state.modelli = carica_modelli()


def normalizza_colonne(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [re.sub(r"\s+", "", str(c)).strip() for c in df.columns]
    if "Contatti" in df.columns and "Telefono" not in df.columns:
        df.rename(columns={"Contatti": "Telefono"}, inplace=True)
    return df


def valore_pulito(v):
    if pd.isna(v):
        return ""
    s = str(v).strip()
    return "" if s.lower() in ["nan", "nat", "none", "null"] else s


def carica_dati():
    try:
        ws = get_worksheet()
        rows = ws.get_all_records()
        df = pd.DataFrame(rows)
        df = normalizza_colonne(df)

        cols = [
            "Cliente", "Impianto", "DataLavaggio", "Orario", "Telefono", "EmailCliente",
            "Promemoria30gg", "DataPromemoria", "DataWA30gg",
            "Promemoria3gg", "DataPromemoria3gg", "DataWA3gg",
            "Stato", "Note", "EventoCalendarioCreato", "DataEventoCreato", "Fornitore",
        ]
        for col in cols:
            if col not in df.columns:
                df[col] = ""

        for col in cols:
            if col != "DataLavaggio":
                df[col] = df[col].apply(valore_pulito)

        df["DataLavaggio_DT"] = pd.to_datetime(df["DataLavaggio"], errors="coerce", dayfirst=True).dt.date
        oggi = date.today()
        df["GiorniMancanti"] = df["DataLavaggio_DT"].apply(lambda x: (x - oggi).days if pd.notna(x) else None)
        df.sort_values(by="DataLavaggio_DT", inplace=True, na_position="last")
        return df
    except Exception as e:
        st.error(f"Errore caricamento Google Sheets: {e}")
        return None


def salva_google_sheets(idx, mappa):
    try:
        ws = get_worksheet()
        headers = ws.row_values(1)
        hdr_reale = {re.sub(r"\s+", "", str(h)).strip().lower(): i + 1 for i, h in enumerate(headers) if h}

        updates = []
        for k, v in mappa.items():
            k_pulito = re.sub(r"\s+", "", k).strip().lower()
            if k_pulito not in hdr_reale:
                nc = len(headers) + 1
                ws.update_cell(1, nc, k)
                headers.append(k)
                hdr_reale[k_pulito] = nc

            # idx è l'indice 0-based originario del dataframe Google: riga reale = idx + 2
            cella = gspread.utils.rowcol_to_a1(int(idx) + 2, hdr_reale[k_pulito])
            updates.append({"range": cella, "values": [[str(v)]]})

        if updates:
            ws.batch_update(updates, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        st.error(f"Errore salvataggio Google Sheets: {e}")
        return False

# Alias per compatibilità con versioni precedenti
salva_excel_sicuro = salva_google_sheets
salva_eccel_sicuro = salva_google_sheets


def pulisci_telefono(n):
    n = str(n).replace(" ", "").replace("+", "").replace(".", "").replace("-", "")
    n = "".join(c for c in n if c.isdigit())
    if n.startswith("3") and len(n) == 10:
        n = "39" + n
    return n


def componi(modello, cliente, data_lavaggio, orario, impianto=""):
    d_s = data_lavaggio.strftime("%d/%m/%Y") if data_lavaggio and pd.notna(data_lavaggio) else ""
    o_s = f"ore {orario}" if orario else ""
    return (
        str(modello)
        .replace("[CLIENTE]", str(cliente))
        .replace("[DATA]", d_s)
        .replace("[ORARIO]", o_s)
        .replace("[IMPIANTO]", str(impianto))
    )


def mailto_url(destinatario, oggetto, corpo):
    return f"mailto:{urllib.parse.quote(str(destinatario))}?subject={urllib.parse.quote(str(oggetto))}&body={urllib.parse.quote(str(corpo))}"


def whatsapp_url(numero, testo):
    tel = pulisci_telefono(numero)
    if not tel:
        return ""
    return f"https://wa.me/{tel}?text={urllib.parse.quote(str(testo))}"


def genera_testo_ics():
    df = st.session_state.df
    if df is None:
        return None
    nuovi = df[
        (df["Stato"].str.upper() == "CONFERMATO DA CLIENTE")
        & (df["EventoCalendarioCreato"].str.upper() != "SI")
    ]
    if nuovi.empty:
        return None

    ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//FV Wash Manager//IT\n"
    for idx, row in nuovi.iterrows():
        dt_lav = row["DataLavaggio_DT"]
        if pd.isna(dt_lav):
            continue
        ora = str(row["Orario"]).replace(":", "")[:4] + "00" if row["Orario"] else "080000"
        uid = f"lavaggio-{idx}-{dt_lav.strftime('%Y%m%d')}@fvwash"
        ics += (
            "BEGIN:VEVENT\n"
            f"UID:{uid}\n"
            f"SUMMARY:LAVAGGIO FV: {row['Cliente']}\n"
            f"DTSTART:{dt_lav.strftime('%Y%m%d')}T{ora}\n"
            f"DESCRIPTION:Impianto: {row['Impianto']}\n"
            "END:VEVENT\n"
        )
    ics += "END:VCALENDAR"
    return ics


def segna_calendario_generato():
    df = st.session_state.df
    if df is None:
        return
    nuovi = df[
        (df["Stato"].str.upper() == "CONFERMATO DA CLIENTE")
        & (df["EventoCalendarioCreato"].str.upper() != "SI")
    ]
    for idx, _ in nuovi.iterrows():
        salva_google_sheets(idx, {
            "EventoCalendarioCreato": "SI",
            "DataEventoCreato": datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
    st.session_state.df = carica_dati()


def badge_status(stato):
    s = valore_pulito(stato).upper()
    if s == "CONFERMATO DA CLIENTE":
        cls = "badge-green"
    elif s == "AVVISATO CLIENTE":
        cls = "badge-blue"
    elif s == "FATTO":
        cls = "badge-gray"
    elif s == "ANNULLATO DA CLIENTE":
        cls = "badge-red"
    elif s == "DA POSTICIPARE":
        cls = "badge-orange"
    else:
        cls = "badge-purple" if s else "badge-gray"
    label = s if s else "DA PROGRAMMARE"
    return f"<span class='badge {cls}'>{html.escape(label)}</span>"


def render_metric(label, value, icon, hint, css_class):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-row">
                <div class="kpi-icon {css_class}">{icon}</div>
                <div>
                    <p class="kpi-label">{html.escape(str(label))}</p>
                    <p class="kpi-value">{html.escape(str(value))}</p>
                </div>
            </div>
            <p class="kpi-hint">{html.escape(str(hint))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_detail(label, value):
    v = valore_pulito(value) or "—"
    st.markdown(
        f"""
        <div class="detail-box">
            <div class="detail-label">{html.escape(str(label))}</div>
            <div class="detail-value">{html.escape(str(v))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def seleziona_lavaggio(idx):
    st.session_state.selected_lavaggio_idx = int(idx)

# ==========================================================
# 5. CARICAMENTO DATI
# ==========================================================
if "df" not in st.session_state:
    st.session_state.df = None
if st.session_state.df is None:
    st.session_state.df = carica_dati()

df = st.session_state.df
if df is None:
    st.error("Google Sheet non trovato o non leggibile. Verifica secrets, permessi e nome foglio.")
    st.stop()

# ==========================================================
# 6. SIDEBAR
# ==========================================================
with st.sidebar:
    st.markdown(
        """
        <div style="padding:18px 10px 22px 10px;">
            <div class="sidebar-logo-3d"></div>
            <div style="font-size:22px;font-weight:900;line-height:1.05;">FV Wash Manager</div>
            <div style="font-size:13px;letter-spacing:3px;color:#93c5fd!important;margin-top:5px;">PORTALE</div>
            <div class="portal-note">Versione web per Google Sites · dati su Google Sheets</div>
        </div>
        <div class="author-mark">M.O.</div>
        """,
        unsafe_allow_html=True,
    )

    pagina = st.radio(
        "Menu",
        ["Dashboard Operativa", "Calendario", "Fornitori", "Modelli Messaggi", "Impostazioni"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown(
        f"""
        <div style="border:1px solid rgba(255,255,255,.16);border-radius:18px;padding:14px;background:rgba(255,255,255,.06);">
            <div style="font-weight:900;margin-bottom:8px;">● Stato sistema</div>
            <div style="font-size:13px;color:#cbd5e1!important;"><span style="color:#22c55e!important;">●</span> Operativo</div>
            <div style="height:14px;"></div>
            <div style="font-size:12px;color:#94a3b8!important;">Google Sheet</div>
            <div style="font-size:13px;">{html.escape(FOGLIO)}</div>
            <div style="height:12px;"></div>
            <div style="font-size:12px;color:#94a3b8!important;">Aggiornamento</div>
            <div style="font-size:13px;">{datetime.now().strftime('%d/%m/%Y %H:%M')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    if SHEET_URL:
        st.link_button("Apri Google Sheet", SHEET_URL, use_container_width=True)
    if st.button("Sincronizza dati", use_container_width=True, type="primary"):
        st.session_state.df = carica_dati()
        st.rerun()

# ==========================================================
# 7. KPI
# ==========================================================
totale = len(df)
completati = len(df[df["Stato"].str.upper() == "FATTO"])
confermati = len(df[df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"])
urgenze = len(df[
    (df["GiorniMancanti"].notna())
    & (df["GiorniMancanti"] >= 0)
    & (df["GiorniMancanti"] <= 5)
    & (df["Stato"].str.upper() != "CONFERMATO DA CLIENTE")
    & (df["Stato"].str.upper() != "FATTO")
])
promemoria_3_da_inviare = len(df[
    (df["GiorniMancanti"].notna())
    & (df["GiorniMancanti"] >= 0)
    & (df["GiorniMancanti"] <= 5)
    & (df["DataPromemoria3gg"].astype(str).str.strip().isin(["", "nan", "NaN"]))
    & (df["Stato"].str.upper() != "FATTO")
])

# ==========================================================
# 8. PAGINE
# ==========================================================
if pagina == "Dashboard Operativa":
    st.markdown(
        """
        <div class="main-title">
            <div class="title-left">
                <h1>Dashboard Operativa</h1>
                <p>Gestione lavaggi FV, promemoria, conferme e fornitori</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        render_metric("Totale Lavaggi", totale, "🧽", "Tutti i record nel foglio", "kpi-blue")
    with m2:
        render_metric("Confermati", confermati, "👍", "Pronti per calendario/fornitore", "kpi-green")
    with m3:
        render_metric("Urgenze", urgenze, "🏃", "Entro 5 giorni non confermati", "kpi-red")
    with m4:
        render_metric("Promemoria", promemoria_3_da_inviare, "🔔", "Da verificare/inviare", "kpi-purple")
    with m5:
        render_metric("Completati", completati, "😌", "Stato FATTO", "kpi-slate")

    st.write("")
    left, right = st.columns([1.02, 1.38], gap="medium")

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title iconless-title">Agenda lavaggi in programma</p>', unsafe_allow_html=True)

        f1, f2 = st.columns([1.4, 1])
        with f1:
            search = st.text_input("Cerca", placeholder="Cliente, impianto, email, telefono...", label_visibility="collapsed")
        with f2:
            filtro_v = st.selectbox(
                "Vista",
                ["Attivi", "Urgenze 3-5 gg", "Prossimi 30 gg", "Confermati", "Completati", "Tutti"],
                label_visibility="collapsed",
            )

        df_view = df.copy()
        if filtro_v == "Attivi":
            df_view = df_view[df_view["Stato"].str.upper() != "FATTO"]
        elif filtro_v == "Urgenze 3-5 gg":
            df_view = df_view[
                (df_view["GiorniMancanti"].notna())
                & (df_view["GiorniMancanti"] >= 0)
                & (df_view["GiorniMancanti"] <= 5)
                & (df_view["Stato"].str.upper() != "CONFERMATO DA CLIENTE")
                & (df_view["Stato"].str.upper() != "FATTO")
            ]
        elif filtro_v == "Prossimi 30 gg":
            df_view = df_view[
                (df_view["GiorniMancanti"].notna())
                & (df_view["GiorniMancanti"] >= 0)
                & (df_view["GiorniMancanti"] <= 30)
                & (df_view["Stato"].str.upper() != "FATTO")
            ]
        elif filtro_v == "Confermati":
            df_view = df_view[df_view["Stato"].str.upper() == "CONFERMATO DA CLIENTE"]
        elif filtro_v == "Completati":
            df_view = df_view[df_view["Stato"].str.upper() == "FATTO"]

        if search:
            mask = (
                df_view["Cliente"].str.contains(search, case=False, na=False)
                | df_view["Impianto"].str.contains(search, case=False, na=False)
                | df_view["EmailCliente"].str.contains(search, case=False, na=False)
                | df_view["Telefono"].str.contains(search, case=False, na=False)
            )
            df_view = df_view[mask]

        if df_view.empty:
            st.info("Nessun lavaggio trovato con i filtri selezionati.")
            selected_idx = None
        else:
            if "selected_lavaggio_idx" not in st.session_state or st.session_state.selected_lavaggio_idx not in list(df_view.index):
                st.session_state.selected_lavaggio_idx = int(df_view.index[0])

            for idx, r in df_view.head(18).iterrows():
                dt = r["DataLavaggio_DT"]
                d = dt.strftime("%d/%m/%Y") if pd.notna(dt) else "—"
                cliente = valore_pulito(r["Cliente"]) or "Cliente non indicato"
                impianto = valore_pulito(r["Impianto"]) or "Impianto non indicato"
                stato = valore_pulito(r["Stato"]).upper() or "DA PROGRAMMARE"
                ora = valore_pulito(r["Orario"]) or "orario non indicato"
                is_selected = int(idx) == int(st.session_state.selected_lavaggio_idx)

                label_card = f"{cliente}\n{d} · {ora}\n{impianto} · {stato}"
                st.button(
                    label_card,
                    key=f"open_lavaggio_{idx}",
                    use_container_width=True,
                    type="primary" if is_selected else "secondary",
                    on_click=seleziona_lavaggio,
                    args=(idx,),
                )

            selected_idx = st.session_state.selected_lavaggio_idx
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<p class="section-title iconless-title">Dettaglio impianto selezionato</p>', unsafe_allow_html=True)

        if selected_idx is None:
            st.info("Seleziona un lavaggio dalla colonna di sinistra.")
        else:
            row = df.loc[selected_idx]
            dt = row["DataLavaggio_DT"]
            st_u = valore_pulito(row["Stato"]).upper()
            giorni_m = row["GiorniMancanti"]
            is_urgent = pd.notna(giorni_m) and 0 <= giorni_m <= 5 and st_u != "CONFERMATO DA CLIENTE" and st_u != "FATTO"

            if is_urgent:
                st.markdown(f"<div class='urgent-box'>Attenzione: mancano {int(giorni_m)} giorni. Inviare o verificare il promemoria.</div>", unsafe_allow_html=True)
            elif st_u == "CONFERMATO DA CLIENTE":
                st.markdown("<div class='ok-box'>Lavaggio confermato: puoi creare evento, avvisare fornitore o segnare FATTO.</div>", unsafe_allow_html=True)

            topa, topb = st.columns([2.4, 1])
            with topa:
                st.markdown(f"<h2 style='margin:0;color:#0f172a;font-size:1.55rem;'>{html.escape(valore_pulito(row['Cliente']) or 'Cliente non indicato')}</h2>", unsafe_allow_html=True)
                st.markdown(f"<div class='small-muted'>{html.escape(valore_pulito(row['Impianto']) or 'Impianto non indicato')}</div>", unsafe_allow_html=True)
            with topb:
                st.markdown(badge_status(row["Stato"]), unsafe_allow_html=True)

            st.write("")
            d1, d2 = st.columns(2)
            with d1:
                render_detail("Data lavaggio", dt.strftime("%d/%m/%Y") if pd.notna(dt) else "")
                render_detail("Orario", row["Orario"])
                render_detail("Telefono", row["Telefono"])
            with d2:
                render_detail("Email", row["EmailCliente"])
                render_detail("Evento calendario", row["EventoCalendarioCreato"])
                render_detail("Fornitore", row.get("Fornitore", ""))

            st.write("")
            st.markdown('<p class="section-title iconless-title">Stato invii</p>', unsafe_allow_html=True)
            inv1, inv2, inv3, inv4 = st.columns(4)
            with inv1:
                render_detail("Mail 30gg", row["DataPromemoria"])
            with inv2:
                render_detail("WA 30gg", row["DataWA30gg"])
            with inv3:
                render_detail("Mail 3gg", row["DataPromemoria3gg"])
            with inv4:
                render_detail("WA 3gg", row["DataWA3gg"])

            st.write("")
            st.markdown('<p class="section-title iconless-title">Azioni rapide</p>', unsafe_allow_html=True)

            stati = ["IN ATTESA CONFERMA", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "DA POSTICIPARE", "ANNULLATO DA CLIENTE"]
            e1, e2, e3 = st.columns(3)
            with e1:
                nuovo_stato = st.selectbox("Stato", stati, index=stati.index(st_u) if st_u in stati else 0, key=f"stato_{selected_idx}")
            with e2:
                nuova_email = st.text_input("Email cliente", valore_pulito(row["EmailCliente"]), key=f"email_{selected_idx}")
            with e3:
                nuovo_tel = st.text_input("Telefono", valore_pulito(row["Telefono"]), key=f"tel_{selected_idx}")

            e4, e5 = st.columns([1, 2])
            with e4:
                nuovo_orario = st.text_input("Orario", valore_pulito(row["Orario"]), key=f"ora_{selected_idx}")
            with e5:
                nuove_note = st.text_input("Note", valore_pulito(row["Note"]), key=f"note_{selected_idx}")

            if st.button("Salva modifiche dettaglio", use_container_width=True, type="primary"):
                esito = salva_google_sheets(selected_idx, {
                    "Stato": nuovo_stato,
                    "EmailCliente": nuova_email,
                    "Telefono": nuovo_tel,
                    "Orario": nuovo_orario,
                    "Note": nuove_note,
                })
                if esito:
                    st.session_state.df = carica_dati()
                    st.success("Modifiche salvate.")
                    st.rerun()

            st.divider()
            tipo = "3" if (pd.notna(giorni_m) and giorni_m <= 5) else "30"
            key_mail = f"mail_link_{selected_idx}"
            key_wa = f"wa_link_{selected_idx}"
            if key_mail not in st.session_state:
                st.session_state[key_mail] = ""
            if key_wa not in st.session_state:
                st.session_state[key_wa] = ""

            a1, a2, a3 = st.columns(3)
            with a1:
                if st.button(f"Mail {tipo} giorni", use_container_width=True, type="primary"):
                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    col_data = "DataPromemoria3gg" if tipo == "3" else "DataPromemoria"
                    col_flag = "Promemoria3gg" if tipo == "3" else "Promemoria30gg"
                    dati = {col_flag: "Si", col_data: now}
                    if nuovo_stato != "CONFERMATO DA CLIENTE":
                        dati["Stato"] = "AVVISATO CLIENTE"
                    if salva_google_sheets(selected_idx, dati):
                        ogg = componi(st.session_state.modelli[f"mail_{tipo}_ogg"], row["Cliente"], dt, nuovo_orario, row["Impianto"])
                        body = componi(st.session_state.modelli[f"mail_{tipo}_txt"], row["Cliente"], dt, nuovo_orario, row["Impianto"])
                        st.session_state[key_mail] = mailto_url(nuova_email, ogg, body)
                        st.session_state.df = carica_dati()
                        st.rerun()
                if st.session_state[key_mail]:
                    st.markdown(f'<a class="clean-link" href="{st.session_state[key_mail]}" target="_blank"><div class="link-button">Apri email</div></a>', unsafe_allow_html=True)

            with a2:
                if st.button(f"WhatsApp {tipo} giorni", use_container_width=True):
                    now = datetime.now().strftime("%d/%m/%Y %H:%M")
                    col_data = "DataWA3gg" if tipo == "3" else "DataWA30gg"
                    col_flag = "Promemoria3gg" if tipo == "3" else "Promemoria30gg"
                    dati = {col_flag: "Si", col_data: now}
                    if nuovo_stato != "CONFERMATO DA CLIENTE":
                        dati["Stato"] = "AVVISATO CLIENTE"
                    if salva_google_sheets(selected_idx, dati):
                        testo = componi(st.session_state.modelli[f"wa_{tipo}_txt"], row["Cliente"], dt, nuovo_orario, row["Impianto"])
                        st.session_state[key_wa] = whatsapp_url(nuovo_tel, testo)
                        st.session_state.df = carica_dati()
                        st.rerun()
                if st.session_state[key_wa]:
                    st.markdown(f'<a class="clean-link" href="{st.session_state[key_wa]}" target="_blank"><div class="link-button-green">Apri WhatsApp</div></a>', unsafe_allow_html=True)

            with a3:
                if st.button("Segna FATTO", use_container_width=True):
                    if salva_google_sheets(selected_idx, {"Stato": "FATTO"}):
                        st.session_state.df = carica_dati()
                        st.success("Lavaggio segnato come FATTO.")
                        st.rerun()

            if nuovo_stato == "CONFERMATO DA CLIENTE":
                f1, f2 = st.columns(2)
                with f1:
                    sel_f = st.selectbox("Fornitore", st.session_state.modelli["fornitori"], key=f"fornitore_{selected_idx}")
                with f2:
                    key_mail_f = f"mail_forn_link_{selected_idx}"
                    if key_mail_f not in st.session_state:
                        st.session_state[key_mail_f] = ""
                    if st.button("Mail fornitore", use_container_width=True):
                        try:
                            mail_f = sel_f.split("(")[1].replace(")", "").strip()
                        except Exception:
                            mail_f = ""
                        if mail_f and salva_google_sheets(selected_idx, {"Fornitore": sel_f.split("(")[0].strip()}):
                            ogg = componi(st.session_state.modelli["mail_forn_ogg"], row["Cliente"], dt, nuovo_orario, row["Impianto"])
                            body = componi(st.session_state.modelli["mail_forn_txt"], row["Cliente"], dt, nuovo_orario, row["Impianto"])
                            st.session_state[key_mail_f] = mailto_url(mail_f, ogg, body)
                            st.session_state.df = carica_dati()
                            st.rerun()
                        elif not mail_f:
                            st.error("Email fornitore non valida.")
                    if st.session_state[key_mail_f]:
                        st.markdown(f'<a class="clean-link" href="{st.session_state[key_mail_f]}" target="_blank"><div class="link-button">Apri email fornitore</div></a>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

elif pagina == "Calendario":
    st.markdown('<div class="main-title"><div class="title-left"><h1>Calendario</h1><p>Esporta gli eventi confermati non ancora creati</p></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    testo_ics = genera_testo_ics()
    if testo_ics:
        st.download_button(
            "Scarica nuovi eventi calendario (.ics)",
            data=testo_ics,
            file_name=f"lavaggi_{date.today()}.ics",
            mime="text/calendar",
            on_click=segna_calendario_generato,
            use_container_width=True,
            type="primary",
        )
        st.info("Esporta solo i lavaggi confermati non ancora segnati come evento creato.")
    else:
        st.success("Nessun nuovo evento calendario da creare.")
    st.markdown("</div>", unsafe_allow_html=True)

elif pagina == "Fornitori":
    st.markdown('<div class="main-title"><div class="title-left"><h1>Resoconto fornitore</h1><p>Genera una mail riepilogativa dei lavaggi confermati</p></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    df_conf = df[df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"]
    st.write(f"Lavaggi confermati disponibili per resoconto: **{len(df_conf)}**")

    if "resoconto_mail_link" not in st.session_state:
        st.session_state["resoconto_mail_link"] = ""

    if st.button("Prepara lista a BG Service", use_container_width=True, type="primary"):
        if df_conf.empty:
            st.warning("Nessun lavaggio confermato al momento.")
        else:
            corpo = "Buongiorno,\ndi seguito il riepilogo dei lavaggi attualmente confermati:\n\n"
            for _, r in df_conf.iterrows():
                d_str = r["DataLavaggio_DT"].strftime("%d/%m/%Y") if pd.notna(r["DataLavaggio_DT"]) else "Data da definire"
                corpo += f"- {d_str} | {r['Cliente']} | Impianto: {r['Impianto']}\n"

            mail_dest = "commerciale@bgservicebergamo.com"
            if st.session_state.modelli.get("fornitori"):
                try:
                    mail_dest = st.session_state.modelli["fornitori"][0].split("(")[1].replace(")", "").strip()
                except Exception:
                    pass
            st.session_state["resoconto_mail_link"] = mailto_url(mail_dest, "Riepilogo Lavaggi Confermati", corpo)
            st.rerun()

    if st.session_state["resoconto_mail_link"]:
        st.markdown(f'<a class="clean-link" href="{st.session_state["resoconto_mail_link"]}" target="_blank"><div class="link-button">Apri email riepilogo fornitore</div></a>', unsafe_allow_html=True)

    st.divider()
    st.dataframe(df_conf.drop(columns=["DataLavaggio_DT", "GiorniMancanti"], errors="ignore"), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

elif pagina == "Modelli Messaggi":
    st.markdown('<div class="main-title"><div class="title-left"><h1>Modelli messaggi</h1><p>Testi usati per mail e WhatsApp</p></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    mod = st.session_state.modelli
    lista_f = st.text_area("Elenco fornitori - formato: Nome (email@test.com)", value="\n".join(mod["fornitori"]), height=110)
    c1, c2 = st.columns(2)
    with c1:
        mod["mail_30_ogg"] = st.text_input("Oggetto mail 30gg", mod["mail_30_ogg"])
        mod["mail_30_txt"] = st.text_area("Testo mail 30gg", mod["mail_30_txt"], height=150)
        mod["mail_3_ogg"] = st.text_input("Oggetto mail 3gg", mod["mail_3_ogg"])
        mod["mail_3_txt"] = st.text_area("Testo mail 3gg", mod["mail_3_txt"], height=150)
    with c2:
        mod["wa_30_txt"] = st.text_area("WhatsApp 30gg", mod["wa_30_txt"], height=150)
        mod["wa_3_txt"] = st.text_area("WhatsApp 3gg", mod["wa_3_txt"], height=150)
        mod["mail_forn_ogg"] = st.text_input("Oggetto mail fornitore", mod["mail_forn_ogg"])
        mod["mail_forn_txt"] = st.text_area("Testo mail fornitore", mod["mail_forn_txt"], height=150)

    if st.button("Salva configurazione", type="primary", use_container_width=True):
        mod["fornitori"] = [x.strip() for x in lista_f.split("\n") if x.strip()]
        try:
            with open(FILE_MODELLI, "w", encoding="utf-8") as f:
                json.dump(mod, f, indent=4, ensure_ascii=False)
            st.success("Configurazione salvata.")
        except Exception:
            st.warning("Configurazione aggiornata in sessione. Sul cloud potrebbe non essere persistente.")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

elif pagina == "Impostazioni":
    st.markdown('<div class="main-title"><div class="title-left"><h1>Impostazioni</h1><p>Diagnostica e dati completi</p></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Google Sheet ID**")
        st.code(SHEET_ID[:8] + "..." if SHEET_ID else "Non configurato")
        st.write("**Foglio dati**")
        st.code(FOGLIO)
    with c2:
        st.write("**Stato Google Sheet**")
        st.success("Configurato") if SHEET_ID else st.error("ID non configurato")
        if SHEET_URL:
            st.link_button("Apri Google Sheet", SHEET_URL)
    st.divider()
    st.subheader("Tabella dati completa")
    st.dataframe(df.drop(columns=["DataLavaggio_DT", "GiorniMancanti"], errors="ignore"), use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
