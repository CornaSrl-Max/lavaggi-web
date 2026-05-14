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
    
    .hero {
        background: linear-gradient(rgba(15,23,42,0.8), rgba(15,23,42,0.8)), 
                    url('https://images.unsplash.com/photo-1509391366360-2e959784a276?q=80&w=1600&auto=format&fit=crop');
        background-size: cover; background-position: center;
        padding: 60px 40px; border-radius: 24px; color: white; text-align: center;
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }
    
    .kpi-box {
        background: white; padding: 20px; border-radius: 18px; text-align: center;
        border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.3s; cursor: pointer;
    }
    .kpi-active { border: 2px solid #2563eb; background: #f0f7ff; transform: translateY(-5px); }
    .kpi-val { font-size: 28px; font-weight: 800; color: #1e293b; margin: 0; }
    .kpi-lab { font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; }

    [data-testid="stSidebar"] { background: #0f172a; }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }

    .card { background: white; border: 1px solid #e2e8f0; border-radius: 20px; padding: 25px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
    
    .stButton>button { border-radius: 12px !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# 3. LOGICA DATI
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
        # Colonne necessarie per la gestione completa
        cols = ["Cliente", "Impianto", "DataLavaggio", "Orario", "Telefono", "EmailCliente", "Stato", 
                "Fornitore", "DataPromemoria", "DataPromemoria3gg", "DataWA30gg", "DataWA3gg", "Note", "EventoCalendarioCreato"]
        for c in cols: 
            if c not in df.columns: df[c] = ""
        df["DataLavaggio_DT"] = pd.to_datetime(df["DataLavaggio"], errors="coerce", dayfirst=True).dt.date
        df["GiorniMancanti"] = df["DataLavaggio_DT"].apply(lambda x: (x - date.today()).days if pd.notna(x) else None)
        return df.sort_values(by="DataLavaggio_DT", na_position="last")
    except Exception as e:
        st.error(f"Errore caricamento: {e}"); return None

def salva_sheet(idx, mappa):
    try:
        ws = get_ws(); headers = ws.row_values(1)
        hdr_map = {re.sub(r"\s+", "", h).strip().lower(): i + 1 for i, h in enumerate(headers)}
        updates = []
        for k, v in mappa.items():
            col = hdr_map.get(k.lower())
            if col: 
                updates.append({"range": gspread.utils.rowcol_to_a1(int(idx) + 2, col), "values": [[str(v)]]})
        if updates: ws.batch_update(updates, value_input_option="USER_ENTERED")
        return True
    except: return False

def carica_modelli():
    d = {
        "fornitori": ["BG Service (commerciale@bgservicebergamo.com)"],
        "mail_30_ogg": "Programmazione lavaggio FV - [CLIENTE]",
        "mail_30_txt": "Gentile cliente, le comunichiamo che il lavaggio è previsto il [DATA] alle [ORARIO].",
        "wa_30_txt": "Buongiorno [CLIENTE], lavaggio FV programmato il *[DATA]* alle *[ORARIO]*.",
        "mail_3_ogg": "Promemoria lavaggio FV - [CLIENTE]",
        "mail_3_txt": "Gentile cliente, le ricordiamo l'appuntamento del [DATA].",
        "wa_3_txt": "Promemoria lavaggio FV per domani *[DATA]*.",
        "mail_forn_ogg": "Conferma intervento - [CLIENTE]",
        "mail_forn_txt": "Buongiorno, confermiamo intervento del [DATA] presso [CLIENTE]."
    }
    if FILE_MODELLI.exists():
        with open(FILE_MODELLI, "r", encoding="utf-8") as f: d.update(json.load(f))
    return d

if "modelli" not in st.session_state: st.session_state.modelli = carica_modelli()

# ==========================================================
# 4. DASHBOARD E SCHEDA CLIENTE
# ==========================================================
if st.session_state.df is None: st.session_state.df = carica_dati()
df = st.session_state.df

with st.sidebar:
    st.markdown("### 🧼 FV Wash Manager")
    pagina = st.radio("Navigazione", ["Dashboard", "Modelli Messaggi", "Calendario", "Impostazioni"])
    if st.button("🔄 Aggiorna Dati"): 
        st.session_state.df = carica_dati(); st.rerun()

if pagina == "Dashboard":
    st.markdown('<div class="hero"><h1>Dashboard Operativa</h1><p>Gestione Interventi e Comunicazioni</p></div>', unsafe_allow_html=True)
    
    # KPI Filtri
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        is_act = "kpi-active" if st.session_state.dash_filter == "Tutti" else ""
        st.markdown(f'<div class="kpi-box {is_act}"><p class="kpi-val">{len(df)}</p><p class="kpi-lab">Totali</p></div>', unsafe_allow_html=True)
        if st.button("Tutti", key="f1"): st.session_state.dash_filter = "Tutti"; st.rerun()
    with c2:
        conf = df[df["Stato"].str.upper().str.contains("CONFERMATO", na=False)]
        is_act = "kpi-active" if st.session_state.dash_filter == "Confermati" else ""
        st.markdown(f'<div class="kpi-box {is_act}"><p class="kpi-val">{len(conf)}</p><p class="kpi-lab">Confermati</p></div>', unsafe_allow_html=True)
        if st.button("Confermati", key="f2"): st.session_state.dash_filter = "Confermati"; st.rerun()
    with c3:
        urg = df[(df["GiorniMancanti"].between(0, 5)) & (~df["Stato"].str.upper().str.contains("FATTO|CONFERMATO", na=False))]
        is_act = "kpi-active" if st.session_state.dash_filter == "Urgenze" else ""
        st.markdown(f'<div class="kpi-box {is_act}"><p class="kpi-val">{len(urg)}</p><p class="kpi-lab">Urgenze</p></div>', unsafe_allow_html=True)
        if st.button("Urgenze", key="f3"): st.session_state.dash_filter = "Urgenze"; st.rerun()
    with c4:
        fatto = df[df["Stato"].str.upper() == "FATTO"]
        is_act = "kpi-active" if st.session_state.dash_filter == "Fatto" else ""
        st.markdown(f'<div class="kpi-box {is_act}"><p class="kpi-val">{len(fatto)}</p><p class="kpi-lab">Completati</p></div>', unsafe_allow_html=True)
        if st.button("Completati", key="f4"): st.session_state.dash_filter = "Fatto"; st.rerun()

    st.divider()

    df_view = df.copy()
    if st.session_state.dash_filter == "Confermati": df_view = conf
    elif st.session_state.dash_filter == "Urgenze": df_view = urg
    elif st.session_state.dash_filter == "Fatto": df_view = fatto

    col_l, col_r = st.columns([1, 1.8], gap="large")
    
    with col_l:
        st.markdown(f"### 📅 Lista: {st.session_state.dash_filter}")
        search = st.text_input("🔍 Cerca Cliente...", placeholder="Scrivi nome...")
        if search: df_view = df_view[df_view["Cliente"].str.contains(search, case=False)]
        
        for idx, r in df_view.head(20).iterrows():
            lbl = f"{r['DataLavaggio']} | {r['Cliente'][:20]}"
            st.button(lbl, key=f"sel_{idx}", use_container_width=True, 
                      on_click=lambda i=idx: st.session_state.update({"selected_idx": i}))

    with col_r:
        if st.session_state.selected_idx is not None:
            row = df.loc[st.session_state.selected_idx]
            st.markdown(f'<div class="card"><h3>SCHEDA CLIENTE: {row["Cliente"]}</h3>', unsafe_allow_html=True)
            
            # --- MODIFICA DATI CLIENTE ---
            c_1, c_2 = st.columns(2)
            new_cliente = c_1.text_input("Nome Cliente", row["Cliente"])
            new_impianto = c_2.text_input("Impianto", row["Impianto"])
            
            c_3, c_4, c_5 = st.columns(3)
            # Conversione data per il date_input
            default_date = row["DataLavaggio_DT"] if pd.notna(row["DataLavaggio_DT"]) else date.today()
            new_date = c_3.date_input("Data Lavaggio", default_date)
            new_ora = c_4.text_input("Orario", row["Orario"])
            new_st = c_5.selectbox("Stato", ["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO"], 
                                   index=["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO"].index(row["Stato"]) if row["Stato"] in ["DA PROGRAMMARE", "AVVISATO CLIENTE", "CONFERMATO DA CLIENTE", "FATTO", "ANNULLATO"] else 0)
            
            c_6, c_7 = st.columns(2)
            new_tel = c_6.text_input("Telefono", row["Telefono"])
            new_mail = c_7.text_input("Email", row["EmailCliente"])
            
            if st.button("💾 AGGIORNA SCHEDA CLIENTE", use_container_width=True, type="primary"):
                mappa = {
                    "Cliente": new_cliente, "Impianto": new_impianto, 
                    "DataLavaggio": new_date.strftime("%d/%m/%Y"), "Orario": new_ora,
                    "Stato": new_st, "Telefono": new_tel, "EmailCliente": new_mail
                }
                if salva_sheet(st.session_state.selected_idx, mappa):
                    st.success("Dati aggiornati!"); st.session_state.df = carica_dati(); st.rerun()
            
            st.divider()
            
            # --- INVIO MESSAGGI E SPUNTA ---
            st.markdown("#### 🚀 Invio Rapido (con spunta automatica)")
            tipo = "3" if (pd.notna(row['GiorniMancanti']) and row['GiorniMancanti'] <= 5) else "30"
            mod = st.session_state.modelli
            
            def componi(t, r, d, o):
                return t.replace("[CLIENTE]", r['Cliente']).replace("[DATA]", d).replace("[ORARIO]", o).replace("[IMPIANTO]", r['Impianto'])

            data_s = new_date.strftime("%d/%m/%Y")
            
            ca, cb = st.columns(2)
            # Logica Email
            if ca.button(f"✉️ Invia Email {tipo}gg"):
                ogg = componi(mod[f"mail_{tipo}_ogg"], row, data_s, new_ora)
                txt = componi(mod[f"mail_{tipo}_txt"], row, data_s, new_ora)
                col_spunta = "DataPromemoria3gg" if tipo == "3" else "DataPromemoria"
                if salva_sheet(st.session_state.selected_idx, {col_spunta: date.today().strftime("%d/%m/%Y"), "Stato": "AVVISATO CLIENTE"}):
                    url = f"mailto:{new_mail}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}"
                    st.markdown(f'<a href="{url}" target="_blank" style="text-decoration:none;"><div style="background:#2563eb;color:white;padding:10px;text-align:center;border-radius:10px;">CLICCA QUI PER APRIRE EMAIL</div></a>', unsafe_allow_html=True)
                    st.toast("Spunta effettuata sullo Sheet!")

            # Logica WhatsApp
            if cb.button(f"💬 Invia WhatsApp {tipo}gg"):
                txt = componi(mod[f"wa_{tipo}_txt"], row, data_s, new_ora)
                num = "".join(filter(str.isdigit, new_tel))
                if num.startswith("3") and len(num) == 10: num = "39" + num
                col_spunta = "DataWA3gg" if tipo == "3" else "DataWA30gg"
                if salva_sheet(st.session_state.selected_idx, {col_spunta: date.today().strftime("%d/%m/%Y"), "Stato": "AVVISATO CLIENTE"}):
                    url = f"https://wa.me/{num}?text={urllib.parse.quote(txt)}"
                    st.markdown(f'<a href="{url}" target="_blank" style="text-decoration:none;"><div style="background:#16a34a;color:white;padding:10px;text-align:center;border-radius:10px;">CLICCA QUI PER APRIRE WHATSAPP</div></a>', unsafe_allow_html=True)
                    st.toast("Spunta effettuata sullo Sheet!")

            st.markdown('</div>', unsafe_allow_html=True)

# ==========================================================
# 5. PAGINA MODELLI MESSAGGI
# ==========================================================
elif pagina == "Modelli Messaggi":
    st.markdown("## 📝 Personalizzazione Messaggi")
    st.info("Qui puoi definire i testi per ogni tipologia di invio. Usa [CLIENTE], [DATA], [ORARIO], [IMPIANTO] come segnaposto.")
    
    mod = st.session_state.modelli
    
    with st.expander("📧 MODELLI EMAIL", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Email 30 giorni")
            mod["mail_30_ogg"] = st.text_input("Oggetto 30gg", mod["mail_30_ogg"])
            mod["mail_30_txt"] = st.text_area("Testo 30gg", mod["mail_30_txt"], height=150)
        with c2:
            st.subheader("Email 3 giorni")
            mod["mail_3_ogg"] = st.text_input("Oggetto 3gg", mod["mail_3_ogg"])
            mod["mail_3_txt"] = st.text_area("Testo 3gg", mod["mail_3_txt"], height=150)

    with st.expander("💬 MODELLI WHATSAPP", expanded=True):
        c3, c4 = st.columns(2)
        with c3:
            st.subheader("WhatsApp 30 giorni")
            mod["wa_30_txt"] = st.text_area("Testo WA 30gg", mod["wa_30_txt"], height=150)
        with c4:
            st.subheader("WhatsApp 3 giorni")
            mod["wa_3_txt"] = st.text_area("Testo WA 3gg", mod["wa_3_txt"], height=150)

    with st.expander("👷 MODELLO FORNITORE"):
        mod["mail_forn_ogg"] = st.text_input("Oggetto Fornitore", mod["mail_forn_ogg"])
        mod["mail_forn_txt"] = st.text_area("Testo Fornitore", mod["mail_forn_txt"], height=150)

    if st.button("💾 SALVA TUTTI I MODELLI", use_container_width=True, type="primary"):
        with open(FILE_MODELLI, "w", encoding="utf-8") as f:
            json.dump(mod, f, indent=4, ensure_ascii=False)
        st.success("Modelli salvati correttamente!")

# PAGINE SECONDARIE (Calendario/Impostazioni come prima)
elif pagina == "Calendario":
    st.markdown("## 📅 Gestione Calendario")
    conf = df[(df["Stato"].str.upper() == "CONFERMATO DA CLIENTE") & (df["EventoCalendarioCreato"] != "SI")]
    if not conf.empty:
        if st.button("Scarica .ics per nuovi eventi"):
            ics = "BEGIN:VCALENDAR\n"
            for i, r in conf.iterrows():
                ics += f"BEGIN:VEVENT\nSUMMARY:Lavaggio {r['Cliente']}\nDTSTART:{str(r['DataLavaggio_DT']).replace('-','')}T080000\nEND:VEVENT\n"
            ics += "END:VCALENDAR"
            st.download_button("Download file", ics, "lavaggi.ics")
    else: st.success("Tutto sincronizzato.")

elif pagina == "Impostazioni":
    st.markdown("## ⚙️ Diagnostica")
    st.write(f"Sheet ID: `{SHEET_ID}`")
    st.write(f"Foglio: `{FOGLIO}`")
    st.dataframe(df)
