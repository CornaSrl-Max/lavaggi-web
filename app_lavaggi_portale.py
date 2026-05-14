# -*- coding: utf-8 -*-
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
# 1. CONFIGURAZIONE E COSTANTI
# ==========================================================
st.set_page_config(
    page_title="FV Wash Manager Platinum+",
    layout="wide",
    page_icon="🧼",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
FILE_MODELLI = BASE_DIR / "modelli_messaggi.json"
SHEET_ID = "16RUw8kcZRurs_LYP9WCGbbLiXZnHEhw_lLEsdlS5Zuc"
FOGLIO = st.secrets.get("google_sheet", {}).get("worksheet_name", "Lavaggi")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Inizializzazione Session State
if "df" not in st.session_state: st.session_state.df = None
if "dash_filter" not in st.session_state: st.session_state.dash_filter = "Tutti"
if "selected_idx" not in st.session_state: st.session_state.selected_idx = None

# ==========================================================
# 2. STILE CSS (PLATINUM UI)
# ==========================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    .stApp { background: #f8fafc; font-family: 'Inter', sans-serif; }
    
    /* Hero Section */
    .hero {
        background: linear-gradient(rgba(15,23,42,0.8), rgba(15,23,42,0.8)), 
                    url('https://images.unsplash.com/photo-1509391366360-2e959784a276?q=80&w=1600&auto=format&fit=crop');
        background-size: cover; background-position: center;
        padding: 60px 40px; border-radius: 24px; color: white; text-align: center;
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }
    
    /* KPI Card Style */
    .kpi-box {
        background: white; padding: 20px; border-radius: 18px; text-align: center;
        border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.3s;
    }
    .kpi-active { border: 2px solid #2563eb; background: #f0f7ff; transform: translateY(-5px); }
    .kpi-val { font-size: 28px; font-weight: 800; color: #1e293b; margin: 0; }
    .kpi-lab { font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; }

    /* Sidebar */
    [data-testid="stSidebar"] { background: #0f172a; }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }

    /* Badges */
    .badge { padding: 4px 12px; border-radius: 99px; font-size: 11px; font-weight: 700; }
    .badge-green { background: #dcfce7; color: #166534; }
    .badge-orange { background: #ffedd5; color: #9a3412; }
    .badge-red { background: #fee2e2; color: #991b1b; }
    .badge-blue { background: #dbeafe; color: #1e40af; }

    /* Main Container */
    .card { background: white; border: 1px solid #e2e8f0; border-radius: 20px; padding: 25px; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# 3. LOGICA DATI E FUNZIONI CORE
# ==========================================================
@st.cache_resource(show_spinner=False)
def get_ws():
    creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(SHEET_ID).worksheet(FOGLIO)

def carica_dati():
    try:
        ws = get_ws()
        df = pd.DataFrame(ws.get_all_records())
        df.columns = [re.sub(r"\s+", "", str(c)).strip() for c in df.columns]
        cols = ["Cliente", "Impianto", "DataLavaggio", "Orario", "Telefono", "EmailCliente", "Stato", "Fornitore", "DataPromemoria", "DataPromemoria3gg", "Note", "EventoCalendarioCreato"]
        for c in cols: 
            if c not in df.columns: df[c] = ""
        df["DataLavaggio_DT"] = pd.to_datetime(df["DataLavaggio"], errors="coerce", dayfirst=True).dt.date
        df["GiorniMancanti"] = df["DataLavaggio_DT"].apply(lambda x: (x - date.today()).days if pd.notna(x) else None)
        return df.sort_values(by="DataLavaggio_DT", na_position="last")
    except Exception as e:
        st.error(f"Errore: {e}"); return None

def salva_sheet(idx, mappa):
    try:
        ws = get_ws(); headers = ws.row_values(1)
        hdr_map = {re.sub(r"\s+", "", h).strip().lower(): i + 1 for i, h in enumerate(headers)}
        updates = []
        for k, v in mappa.items():
            col = hdr_map.get(k.lower())
            if col: updates.append({"range": gspread.utils.rowcol_to_a1(int(idx) + 2, col), "values": [[str(v)]]})
        if updates: ws.batch_update(updates, value_input_option="USER_ENTERED")
        return True
    except: return False

def carica_modelli():
    d = {"fornitori": ["BG Service (commerciale@bgservicebergamo.com)"], "mail_30_ogg": "Lavaggio FV [CLIENTE]", "mail_30_txt": "Lavaggio il [DATA] [ORARIO]", "wa_30_txt": "Lavaggio il [DATA]", "mail_3_ogg": "Promemoria [CLIENTE]", "mail_3_txt": "Ricordiamo il [DATA]", "wa_3_txt": "Ricordo lavaggio [DATA]", "mail_forn_ogg": "Intervento [CLIENTE]", "mail_forn_txt": "Intervento [DATA]"}
    if FILE_MODELLI.exists():
        with open(FILE_MODELLI, "r", encoding="utf-8") as f: d.update(json.load(f))
    return d

if "modelli" not in st.session_state: st.session_state.modelli = carica_modelli()

# ==========================================================
# 4. PAGINE
# ==========================================================
if st.session_state.df is None: st.session_state.df = carica_dati()
df = st.session_state.df

with st.sidebar:
    st.markdown("### 🧼 FV Wash Manager")
    pagina = st.radio("Menu", ["Dashboard", "Calendario", "Fornitori", "Modelli Messaggi", "Impostazioni"])
    if st.button("🔄 Aggiorna Dati"): 
        st.session_state.df = carica_dati()
        st.rerun()

if pagina == "Dashboard":
    st.markdown('<div class="hero"><h1>Dashboard Operativa</h1><p>Seleziona una categoria per filtrare l\'agenda</p></div>', unsafe_allow_html=True)
    
    # --- KPI INTERATTIVI (FILTRI) ---
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        is_act = "kpi-active" if st.session_state.dash_filter == "Tutti" else ""
        st.markdown(f'<div class="kpi-box {is_act}"><p class="kpi-val">{len(df)}</p><p class="kpi-lab">Totali</p></div>', unsafe_allow_html=True)
        if st.button("Mostra Tutti", use_container_width=True): st.session_state.dash_filter = "Tutti"; st.rerun()

    with c2:
        conf = df[df["Stato"].str.upper().str.contains("CONFERMATO", na=False)]
        is_act = "kpi-active" if st.session_state.dash_filter == "Confermati" else ""
        st.markdown(f'<div class="kpi-box {is_act}"><p class="kpi-val">{len(conf)}</p><p class="kpi-lab">Confermati</p></div>', unsafe_allow_html=True)
        if st.button("Solo Confermati", use_container_width=True): st.session_state.dash_filter = "Confermati"; st.rerun()

    with c3:
        urg = df[(df["GiorniMancanti"].between(0, 5)) & (~df["Stato"].str.upper().str.contains("FATTO|CONFERMATO", na=False))]
        is_act = "kpi-active" if st.session_state.dash_filter == "Urgenze" else ""
        st.markdown(f'<div class="kpi-box {is_act}"><p class="kpi-val">{len(urg)}</p><p class="kpi-lab">Urgenze</p></div>', unsafe_allow_html=True)
        if st.button("Vedi Urgenze", use_container_width=True): st.session_state.dash_filter = "Urgenze"; st.rerun()

    with c4:
        fatto = df[df["Stato"].str.upper() == "FATTO"]
        is_act = "kpi-active" if st.session_state.dash_filter == "Fatto" else ""
        st.markdown(f'<div class="kpi-box {is_act}"><p class="kpi-val">{len(fatto)}</p><p class="kpi-lab">Completati</p></div>', unsafe_allow_html=True)
        if st.button("Vedi Fatti", use_container_width=True): st.session_state.dash_filter = "Fatto"; st.rerun()

    st.divider()

    # --- APPLICAZIONE FILTRO ALL'AGENDA ---
    df_view = df.copy()
    if st.session_state.dash_filter == "Confermati": df_view = conf
    elif st.session_state.dash_filter == "Urgenze": df_view = urg
    elif st.session_state.dash_filter == "Fatto": df_view = fatto

    col_l, col_r = st.columns([1, 1.6], gap="large")
    
    with col_l:
        st.markdown(f"### 📅 Agenda: {st.session_state.dash_filter}")
        search = st.text_input("🔍 Cerca...", placeholder="Cliente...")
        if search: df_view = df_view[df_view["Cliente"].str.contains(search, case=False)]
        
        for idx, r in df_view.head(20).iterrows():
            st.button(f"{r['DataLavaggio']} | {r['Cliente'][:20]}", key=f"btn_{idx}", 
                      use_container_width=True, on_click=lambda i=idx: st.session_state.update({"selected_idx": i}))

    with col_r:
        if st.session_state.selected_idx is not None:
            row = df.loc[st.session_state.selected_idx]
            st.markdown(f'<div class="card"><h2>{row["Cliente"]}</h2><p>{row["Impianto"]}</p>', unsafe_allow_html=True)
            
            # Form Modifica
            c_a, c_b = st.columns(2)
            new_st = c_a.selectbox("Stato", ["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO"], 
                                   index=["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO"].index(row["Stato"]) if row["Stato"] in ["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO"] else 0)
            new_ora = c_b.text_input("Orario", row["Orario"])
            new_tel = c_a.text_input("Telefono", row["Telefono"])
            new_mail = c_b.text_input("Email", row["EmailCliente"])
            
            if st.button("💾 Salva Dati", use_container_width=True, type="primary"):
                if salva_sheet(st.session_state.selected_idx, {"Stato": new_st, "Orario": new_ora, "Telefono": new_tel, "EmailCliente": new_mail}):
                    st.success("Salvato!"); st.session_state.df = carica_dati(); st.rerun()
            
            st.divider()
            # Bottoni Comunicazione
            tipo = "3" if (pd.notna(row['GiorniMancanti']) and row['GiorniMancanti'] <= 5) else "30"
            ca, cb = st.columns(2)
            if ca.button(f"✉️ Email {tipo}gg"):
                url = f"mailto:{new_mail}?subject={row['Cliente']}&body=Lavaggio il {row['DataLavaggio']}"
                st.markdown(f'[Apri Email]({url})')
            if cb.button(f"💬 WA {tipo}gg"):
                num = "".join(filter(str.isdigit, new_tel))
                st.markdown(f'[Apri WhatsApp](https://wa.me/{num})')
            st.markdown('</div>', unsafe_allow_html=True)

elif pagina == "Calendario":
    st.markdown("## 📅 Esportazione ICS")
    conf = df[(df["Stato"].str.upper() == "CONFERMATO DA CLIENTE") & (df["EventoCalendarioCreato"] != "SI")]
    if not conf.empty:
        ics = "BEGIN:VCALENDAR\n"
        for i, r in conf.iterrows():
            ics += f"BEGIN:VEVENT\nSUMMARY:Lavaggio {r['Cliente']}\nDTSTART:{str(r['DataLavaggio_DT']).replace('-','')}T080000\nEND:VEVENT\n"
        ics += "END:VCALENDAR"
        st.download_button("Download .ics", ics, "eventi.ics", on_click=lambda: [salva_sheet(i, {"EventoCalendarioCreato": "SI"}) for i in conf.index])
    else: st.success("Tutto sincronizzato col calendario.")

elif pagina == "Modelli Messaggi":
    st.markdown("## 📝 Configurazione Messaggi")
    mod = st.session_state.modelli
    mod["mail_30_ogg"] = st.text_input("Oggetto 30gg", mod["mail_30_ogg"])
    mod["mail_30_txt"] = st.text_area("Testo 30gg", mod["mail_30_txt"])
    if st.button("💾 Salva Modelli"):
        with open(FILE_MODELLI, "w", encoding="utf-8") as f: json.dump(mod, f, indent=4)
        st.success("Modelli salvati!")

elif pagina == "Fornitori":
    st.markdown("## 👷 BG Service Report")
    conf = df[df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"]
    if st.button("Genera Riepilogo Email"):
        txt = "Interventi confermati:\n" + "\n".join([f"- {r['DataLavaggio']}: {r['Cliente']}" for i, r in conf.iterrows()])
        st.code(txt)

elif pagina == "Impostazioni":
    st.markdown("## ⚙️ Diagnostica")
    st.write(f"Sheet ID: `{SHEET_ID}`")
    st.dataframe(df)
