# ==========================================================
# 8. DASHBOARD
# ==========================================================
if pagina == "Dashboard":
    st.markdown(
        '<div class="hero"><h1>FV WASH MANAGER</h1><p>Controllo Operativo Interventi</p></div>',
        unsafe_allow_html=True,
    )

    oggi = date.today()
    urg_no_mail = df[
        (df["GiorniMancanti"].between(0, 5))
        & (df["DataPromemoria3gg"] == "")
        & (df["Stato"].str.upper() != "FATTO")
    ]
    manca_30gg = df[
        (df["GiorniMancanti"] > 15)
        & (df["DataPromemoria"] == "")
        & (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")
    ]
    task_scadenza = pd.DataFrame()
    if "Task_Due_DT" in df.columns:
        task_scadenza = df[
            df["Task_Due_DT"].apply(
                lambda x: pd.notna(x)
                and (x - oggi).days <= 3
                and (x - oggi).days >= -1
            )
        ]

    if (
        not urg_no_mail.empty
        or not manca_30gg.empty
        or not task_scadenza.empty
    ):
        st.markdown("### ⚠️ Centro Avvisi (Clicca per gestire)")
        c_al1, c_al2, c_al3 = st.columns(3)
        with c_al1:
            if not urg_no_mail.empty:
                if st.button(
                    f"🚨 Reminder 3gg mancanti: {len(urg_no_mail)}",
                    type="primary",
                ):
                    st.session_state.dash_filter = "Alert: Reminder 3gg"
                    st.rerun()
        with c_al2:
            if not manca_30gg.empty:
                if st.button(
                    f"📧 Avvisi 30gg mancanti: {len(manca_30gg)}"
                ):
                    st.session_state.dash_filter = "Alert: Avvisi 30gg"
                    st.rerun()
        with c_al3:
            if not task_scadenza.empty:
                if st.button(
                    f"🔔 Reminder Task scadenza: {len(task_scadenza)}"
                ):
                    st.session_state.dash_filter = "Alert: Task Reminder"
                    st.rerun()
        st.divider()

    df_tutti = df.sort_values(by="Cliente")
    df_conf = df[
        df["Stato"].str.upper() == "CONFERMATO DA CLIENTE"
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    df_urg = df[
        (df["GiorniMancanti"].between(0, 15))
        & (df["Stato"].str.upper() != "CONFERMATO DA CLIENTE")
        & (df["Stato"].str.upper() != "FATTO")
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    df_comp = df[
        df["Stato"].str.upper() == "FATTO"
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    df_da_fare = df[
        (df["Stato"].str.upper() != "FATTO")
        & (df["Stato"].str.upper() != "ANNULLATO DA CLIENTE")
    ].sort_values(by="DataLavaggio_DT", na_position="last")
    df_annullati = df[
        df["Stato"].str.upper() == "ANNULLATO DA CLIENTE"
    ].sort_values(by="DataLavaggio_DT", na_position="last")

    k_cols = st.columns(6)
    kpis = [
        ("Tutti", "📋", len(df_tutti)),
        ("Confermati", "👍", len(df_conf)),
        ("Urgenze", "🔥", len(df_urg)),
        ("Completati", "✅", len(df_comp)),
        ("Da Fare", "🛠️", len(df_da_fare)),
        ("Annullati", "❌", len(df_annullati)),
    ]
    for i, (name, icon, count) in enumerate(kpis):
        with k_cols[i]:
            act = "kpi-active" if st.session_state.dash_filter == name else ""
            st.markdown(
                f'<div class="kpi-box {act}"><span class="kpi-icon">{icon}</span><p class="kpi-val">{count}</p><p class="kpi-lab">{name}</p></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                name, key=f"f_{name}", use_container_width=True
            ):
                st.session_state.dash_filter = name
                st.rerun()

    st.divider()

    if st.session_state.dash_filter == "Alert: Reminder 3gg":
        df_view = urg_no_mail.sort_values(by="DataLavaggio_DT")
    elif st.session_state.dash_filter == "Alert: Avvisi 30gg":
        df_view = manca_30gg.sort_values(by="DataLavaggio_DT")
    elif st.session_state.dash_filter == "Alert: Task Reminder":
        df_view = task_scadenza.sort_values(by="Task_Due_DT")
    elif st.session_state.dash_filter == "Tutti":
        df_view = df_tutti
    elif st.session_state.dash_filter == "Confermati":
        df_view = df_conf
    elif st.session_state.dash_filter == "Urgenze":
        df_view = df_urg
    elif st.session_state.dash_filter == "Completati":
        df_view = df_comp
    elif st.session_state.dash_filter == "Da Fare":
        df_view = df_da_fare
    else:
        df_view = df_annullati

    mask_sospesi = (df_view["DataLavaggio"] == "") | (
        df_view["Stato"].str.upper().isin(
            ["DA PROGRAMMARE", "ANNULLATO DA CLIENTE"]
        )
    )
    df_attivi = df_view[~mask_sospesi]
    df_sospesi = df_view[mask_sospesi]

    col_l, col_r = st.columns([1, 1.8], gap="large")
    with col_l:
        st.markdown(f"### 📅 {st.session_state.dash_filter}")
        search = st.text_input("🔍 Cerca...", placeholder="Filtra Cliente...")
        if search:
            df_attivi = df_attivi[
                df_attivi["Cliente"].str.contains(search, case=False)
            ]
            df_sospesi = df_sospesi[
                df_sospesi["Cliente"].str.contains(search, case=False)
            ]

        for idx, r in df_attivi.head(45).iterrows():
            st_u = str(r["Stato"]).upper()
            gm = r["GiorniMancanti"]
            if st_u == "FATTO":
                dot = "🟢"
            elif st_u == "ANNULLATO DA CLIENTE":
                dot = "⚪"
            elif gm is not None and (
                gm < 0 or (gm <= 3 and st_u != "CONFERMATO DA CLIENTE")
            ):
                dot = "🔴"
            elif r["DataPromemoria"] == "" and r["DataWA30gg"] == "":
                dot = "🟡"
            else:
                dot = "🟢"

            lbl = f"{dot}   {r['DataLavaggio']}      {str(r['Cliente']).upper()}"
            st.button(
                lbl,
                key=f"sel_{idx}",
                use_container_width=True,
                on_click=lambda i=idx: st.session_state.update(
                    {"selected_idx": i}
                ),
            )

        if (
            not df_sospesi.empty
            and st.session_state.dash_filter
            in ["Tutti", "Da Fare", "Annullati"]
        ):
            with st.expander("📁 SOSPESI / ANNULLATI"):
                for idx, r in df_sospesi.iterrows():
                    lbl = f"⚪   [{r['Stato'] or '??'}]      {str(r['Cliente']).upper()}"
                    st.button(
                        lbl,
                        key=f"sel_{idx}",
                        use_container_width=True,
                        on_click=lambda i=idx: st.session_state.update(
                            {"selected_idx": i}
                        ),
                    )

    with col_r:
        if st.session_state.selected_idx is not None:
            row = df.loc[st.session_state.selected_idx]
            st.markdown(
                f'<div class="card"><h2 style="margin-top:0;">{row["Cliente"]}</h2>',
                unsafe_allow_html=True,
            )
            
            # --- INIZIO BLOCCO RIPRISTINATO: STORICO INVII ---
            st.markdown("#### 📡 Storico Invii Promemoria")
            i1, i2, i3, i4 = st.columns(4)
            
            def val_invio(v):
                return str(v).strip() if pd.notna(v) and str(v).strip() else "—"
                
            box_style = "background:#f8fafc; padding:12px 8px; border-radius:12px; border:1px solid #e2e8f0; text-align:center; line-height:1.4;"
            lbl_style = "font-size:11px; color:#64748b; font-weight:700; text-transform:uppercase;"
            val_style = "font-size:14px; font-weight:800; color:#0f172a;"
            
            i1.markdown(f"<div style='{box_style}'><span style='{lbl_style}'>Mail 30gg</span><br/><span style='{val_style}'>{val_invio(row['DataPromemoria'])}</span></div>", unsafe_allow_html=True)
            i2.markdown(f"<div style='{box_style}'><span style='{lbl_style}'>WA 30gg</span><br/><span style='{val_style}'>{val_invio(row['DataWA30gg'])}</span></div>", unsafe_allow_html=True)
            i3.markdown(f"<div style='{box_style}'><span style='{lbl_style}'>Mail 3gg</span><br/><span style='{val_style}'>{val_invio(row['DataPromemoria3gg'])}</span></div>", unsafe_allow_html=True)
            i4.markdown(f"<div style='{box_style}'><span style='{lbl_style}'>WA 3gg</span><br/><span style='{val_style}'>{val_invio(row['DataWA3gg'])}</span></div>", unsafe_allow_html=True)
            
            st.write("")
            # --- FINE BLOCCO STORICO INVII ---

            c1, c2 = st.columns(2)
            n_cl = c1.text_input(
                "Nome Cliente",
                row["Cliente"],
                disabled=not can_edit_client,
            )
            n_im = c2.text_input(
                "Impianto", row["Impianto"], disabled=not can_edit_client
            )
            c3, c4, c5 = st.columns(3)
            d_dt = (
                row["DataLavaggio_DT"]
                if pd.notna(row["DataLavaggio_DT"])
                else date.today()
            )
            n_dt = c3.date_input(
                "Data Lavaggio",
                d_dt,
                format="DD/MM/YYYY",
                disabled=not can_edit_client,
            )
            n_or = c4.text_input(
                "Orario", row["Orario"], disabled=not can_edit_client
            )
            st_list = [
                "DA PROGRAMMARE",
                "AVVISATO CLIENTE",
                "CONFERMATO DA CLIENTE",
                "FATTO",
                "ANNULLATO DA CLIENTE",
            ]
            curr_st = (
                row["Stato"]
                if row["Stato"] in st_list
                else "DA PROGRAMMARE"
            )
            st_cls = "st-da-programmare"
            if "AVVISATO" in curr_st:
                st_cls = "st-avvisato"
            elif "CONFERMATO" in curr_st:
                st_cls = "st-confermato"
            elif "FATTO" in curr_st:
                st_cls = "st-fatto"
            elif "ANNULLATO" in curr_st:
                st_cls = "st-annullato"
            with c5:
                st.markdown(
                    f'<div class="status-container {st_cls}">{curr_st}</div>',
                    unsafe_allow_html=True,
                )
                n_st = st.selectbox(
                    "Cambia Stato",
                    st_list,
                    index=st_list.index(curr_st),
                    label_visibility="collapsed",
                    disabled=not can_edit_client,
                )
            c6, c7 = st.columns(2)
            n_tel = c6.text_input(
                "Telefono", row["Telefono"], disabled=not can_edit_client
            )
            n_ml = c7.text_input(
                "Email", row["EmailCliente"], disabled=not can_edit_client
            )
            n_note = st.text_area(
                "Note",
                row["Note"],
                height=70,
                disabled=not can_edit_client,
            )

            st.markdown("#### 🔔 Reminder Custom")
            c_tr, c_td = st.columns([2, 1])
            n_tr = c_tr.text_input(
                "Azione", row["Task_Rem"], disabled=not can_send_comms
            )
            n_td = c_td.date_input(
                "Scadenza",
                row["Task_Due_DT"] if pd.notna(row["Task_Due_DT"]) else None,
                format="DD/MM/YYYY",
                disabled=not can_send_comms,
            )

            if st.button(
                "💾 AGGIORNA DATI CLIENTE",
                type="primary",
                disabled=not can_edit_client,
            ):
                if salva_sheet(
                    st.session_state.selected_idx,
                    {
                        "Cliente": n_cl,
                        "Impianto": n_im,
                        "DataLavaggio": n_dt.strftime("%d/%m/%Y"),
                        "Orario": n_or,
                        "Stato": n_st,
                        "Telefono": n_tel,
                        "EmailCliente": n_ml,
                        "Note": n_note,
                        "Task_Rem": n_tr,
                        "Task_Due": n_td.strftime("%d/%m/%Y")
                        if n_td
                        else "",
                    },
                ):
                    st.session_state.df = carica_dati()
                    st.rerun()

            st.divider()
            st.markdown("#### 🚀 Invio Comunicazioni")
            tipo = (
                "3"
                if (
                    pd.notna(row["GiorniMancanti"])
                    and row["GiorniMancanti"] <= 5
                )
                else "30"
            )
            mod = st.session_state.modelli

            def comp(t, r, d, o):
                return (
                    t.replace("[CLIENTE]", r["Cliente"])
                    .replace("[DATA]", d)
                    .replace("[ORARIO]", o)
                    .replace("[IMPIANTO]", r["Impianto"])
                )

            ca, cb, cc = st.columns(3)
            if ca.button(
                f"✉️ Email {tipo}gg", disabled=not can_send_comms
            ):
                ogg = comp(
                    mod[f"mail_{tipo}_ogg"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                txt = comp(
                    mod[f"mail_{tipo}_txt"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                if salva_sheet(
                    st.session_state.selected_idx,
                    {
                        "DataPromemoria"
                        + ("3gg" if tipo == "3" else ""): date.today().strftime(
                            "%d/%m/%Y"
                        ),
                        "Stato": "AVVISATO CLIENTE",
                    },
                ):
                    registra_log("Invio Email", f"Inviato preavviso {tipo}gg a {row['Cliente']}")
                    st.markdown(
                        f'<a href="mailto:{n_ml}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}" target="_blank" style="text-decoration:none;"><div style="background:#2563eb;color:white;padding:12px;text-align:center;border-radius:12px;font-weight:700;">APRI EMAIL</div></a>',
                        unsafe_allow_html=True,
                    )
            if cb.button(
                f"💬 WhatsApp {tipo}gg", disabled=not can_send_comms
            ):
                txt = comp(
                    mod[f"wa_{tipo}_txt"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                num = "".join(filter(str.isdigit, n_tel))
                if num.startswith("3") and len(num) == 10:
                    num = "39" + num
                if salva_sheet(
                    st.session_state.selected_idx,
                    {
                        "DataWA"
                        + tipo
                        + "gg": date.today().strftime("%d/%m/%Y"),
                        "Stato": "AVVISATO CLIENTE",
                    },
                ):
                    registra_log("Invio WhatsApp", f"Inviato preavviso {tipo}gg a {row['Cliente']}")
                    url = f"https://wa.me/{num}?text={urllib.parse.quote(txt)}"
                    st.markdown(
                        f'<a href="{url}" target="_blank" style="text-decoration:none;"><div style="background:#16a34a;color:white;padding:12px;text-align:center;border-radius:12px;font-weight:700;">APRI WHATSAPP</div></a>',
                        unsafe_allow_html=True,
                    )
            if cc.button(
                "👷 Email Fornitore",
                disabled=not can_send_comms
                or n_st != "CONFERMATO DA CLIENTE",
            ):
                ogg = comp(
                    mod["mail_forn_ogg"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                txt = comp(
                    mod["mail_forn_txt"],
                    row,
                    n_dt.strftime("%d/%m/%Y"),
                    n_or,
                )
                registra_log("Invio Fornitore", f"Generata mail fornitore per impianto {row['Cliente']}")
                st.markdown(
                    f'<a href="mailto:{mod["mail_fornitore"]}?subject={urllib.parse.quote(ogg)}&body={urllib.parse.quote(txt)}" target="_blank" style="text-decoration:none;"><div style="background:#475569;color:white;padding:12px;text-align:center;border-radius:12px;font-weight:700;">AVVISA FORNITORE</div></a>',
                    unsafe_allow_html=True,
                )
            
            st.markdown('</div>', unsafe_allow_html=True)
