            df_f[["DataLavaggio", "Orario", "Cliente", "Impianto", "Stato"]],
            use_container_width=True,
        )

        testo = "Buongiorno,\ndi seguito il riepilogo dei lavaggi dei prossimi 30 giorni:\n\n"

        for _, r in df_f.iterrows():
            testo += f"- {r['DataLavaggio']} {r['Orario']}: {r['Cliente']} | {r['Impianto']} | Stato: {r['Stato']}\n"

        if st.button("Genera Email Fornitore", disabled=not can_send_comms):
            st.code(testo)
            url = (
                f"mailto:{st.session_state.modelli['mail_fornitore']}"
                f"?subject=Riepilogo Lavaggi 30gg"
                f"&body={urllib.parse.quote(testo)}"
            )
            st.markdown(f'<a href="{url}" target="_blank" class="action-link action-supplier">INVIA AL FORNITORE</a>', unsafe_allow_html=True)


# ==========================================================
# 11. CALENDARIO
# ==========================================================
elif pagina == "Calendario":
    st.title("📅 Esporta Calendario")

    conf = df[
        (df["Stato"].astype(str).str.upper() == "CONFERMATO DA CLIENTE")
        & (df["EventoCalendarioCreato"].astype(str).str.upper() != "SI")
    ]

    if conf.empty:
        st.info("Nessun nuovo evento confermato da esportare.")
    else:
        ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//FV Wash Manager//IT\n"

        for _, r in conf.iterrows():
            dt = r["DataLavaggio_DT"]

            if pd.notna(dt):
                data_ics = str(dt).replace("-", "")
                ics += (
                    "BEGIN:VEVENT\n"
                    f"SUMMARY:Lavaggio {r['Cliente']}\n"
                    f"DTSTART:{data_ics}T080000\n"
                    f"DTEND:{data_ics}T090000\n"
                    "END:VEVENT\n"
                )

        ics += "END:VCALENDAR"

        if st.download_button("Scarica .ics", ics, "lavaggi.ics", disabled=not can_send_comms):
            for i in conf.index:
                salva_sheet(
                    i,
                    {
                        "EventoCalendarioCreato": "SI",
                        "DataEventoCreato": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    },
                )

            st.success("Eventi segnati come esportati.")


# ==========================================================
# 12. GESTIONE UTENTI
# ==========================================================
elif pagina == "Gestione Utenti":
    st.title("👤 Gestione Utenti")

    if not is_admin:
        st.warning("Accesso riservato agli amministratori.")
        st.stop()

    utenti = carica_utenti()

    if utenti.empty:
        st.warning("Nessun utente trovato.")
    else:
        st.dataframe(
            utenti[["username", "ruolo"]],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.markdown("### Nuovo utente / modifica utente")

    lista_utenti = ["Nuovo utente"]

    if not utenti.empty:
        lista_utenti += utenti["username"].tolist()

    scelta = st.selectbox("Seleziona utente", lista_utenti)

    if scelta == "Nuovo utente":
        username = st.text_input("Username")
        ruolo = st.selectbox("Ruolo", ["user", "supervisor", "admin"])
        password = st.text_input("Password", type="password")
        conferma = st.text_input("Conferma password", type="password")

        if st.button("➕ CREA UTENTE", type="primary"):
            if password != conferma:
                st.error("Le password non coincidono.")
            elif salva_utente(username, password, ruolo):
                st.success("Utente creato.")
                st.rerun()

    else:
        record = utenti[utenti["username"] == scelta].iloc[0]

        username = st.text_input("Username", record["username"], disabled=True)

        ruolo_corrente = record["ruolo"] if record["ruolo"] in ["user", "supervisor", "admin"] else "user"

        ruolo = st.selectbox(
            "Ruolo",
            ["user", "supervisor", "admin"],
            index=["user", "supervisor", "admin"].index(ruolo_corrente),
        )

        st.info("Lascia vuota la password se vuoi modificare solo il ruolo.")

        nuova_password = st.text_input("Nuova password", type="password")
        conferma_password = st.text_input("Conferma nuova password", type="password")

        c1, c2 = st.columns(2)

        with c1:
            if st.button("💾 SALVA MODIFICHE", type="primary"):
                if nuova_password and nuova_password != conferma_password:
                    st.error("Le password non coincidono.")
                elif salva_utente(username, nuova_password, ruolo):
                    st.success("Utente aggiornato.")
                    st.rerun()

        with c2:
            if st.button("🗑️ ELIMINA UTENTE"):
                if elimina_utente(username):
                    st.success("Utente eliminato.")
                    st.rerun()


# ==========================================================
# 13. IMPOSTAZIONI
# ==========================================================
elif pagina == "Impostazioni":
    st.title("⚙️ Diagnostica")

    st.write(f"Utente: **{st.session_state.utente or 'ospite'}**")
    st.write(f"Ruolo: **{st.session_state.ruolo}**")
    st.write(f"Foglio lavaggi: **{FOGLIO_LAVAGGI}**")
    st.write(f"Foglio utenti: **{FOGLIO_UTENTI}**")
    st.write(f"Foglio modelli: **{FOGLIO_MODELLI}**")

    st.dataframe(df, use_container_width=True)
