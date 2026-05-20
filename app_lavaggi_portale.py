d = {
"fornitori": ["BG Service (commerciale@bgservicebergamo.com)"],
"mail_fornitore": "commerciale@bgservicebergamo.com",
"mail_30_ogg": "Lavaggio FV [CLIENTE]",
"mail_30_txt": "Lavaggio il [DATA]",
"wa_30_txt": "Lavaggio [DATA]",
"mail_3_ogg": "Promemoria [CLIENTE]",
"mail_3_txt": "Ricordiamo [DATA]",
"wa_3_txt": "Promemoria domani [DATA]",
"mail_forn_ogg": "Intervento [CLIENTE]",
"mail_forn_txt": "Intervento [DATA]",
}
if FILE_MODELLI.exists():
try:
with open(FILE_MODELLI, "r", encoding="utf-8") as f:
d.update(json.load(f))
except Exception:
st.warning("File modelli corrotto, ripristinati valori di default.")
return d

if "modelli" not in st.session_state:
st.session_state.modelli = carica_modelli()

# ==========================================================
# 5. SIDEBAR E NAVIGAZIONE
# 5. SIDEBAR E NAVIGAZIONE (Modificata per Link GSheet protetto)
# ==========================================================
with st.sidebar:
st.markdown("### 🧼 FV WASH MANAGER")
@@ -311,7 +311,7 @@

st.divider()

    # Creazione della lista delle pagine, inclusa Log di Sistema se l'utente è Admin
    # Lista pagine dinamica
lista_pagine = [
"Dashboard",
"Modelli Messaggi",
@@ -326,11 +326,16 @@

pagina = st.radio("Navigazione", lista_pagine)
st.divider()
    st.link_button("📊 Apri Google Sheet", SHEET_URL, use_container_width=True)

    # --- MODIFICA RICHIESTA: Link visibile solo all'Admin ---
    if st.session_state.ruolo == "admin":
        st.link_button("📊 Apri Google Sheet", SHEET_URL, use_container_width=True)
        st.write("") # Piccolo spazio estetico
    # -------------------------------------------------------

if st.button("🔄 Aggiorna Dati"):
st.session_state.df = carica_dati()
st.rerun()

# ==========================================================
# 6. PERMESSI
# ==========================================================
