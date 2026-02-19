import streamlit as st
import pandas as pd
import logic
import time

def render_view():
    st.header("✏️ Gestión Dinámica de Tickets")

    # --- 1. FILTRO DE CASA ---
    opciones_casas = logic.db.run_query("SELECT id, nombre FROM casas_general ORDER BY id", return_data=True)
    dict_casas = dict(zip(opciones_casas['nombre'], opciones_casas['id']))
    
    col_filter, col_vacia = st.columns([1, 2])
    with col_filter:
        # Lógica para mantener la selección
        index_defecto = 0
        if "casa_seleccionada_index" in st.session_state:
             try:
                 lista_nombres = list(dict_casas.keys())
                 if st.session_state.casa_seleccionada_index in lista_nombres:
                     index_defecto = lista_nombres.index(st.session_state.casa_seleccionada_index)
             except: pass

        casa_seleccionada = st.selectbox("🏡 Selecciona la Casa a Editar:", list(dict_casas.keys()), index=index_defecto)
        st.session_state.casa_seleccionada_index = casa_seleccionada
        id_casa_actual = int(dict_casas[casa_seleccionada])

    st.divider()

    # --- 2. CARGAR DATOS ---
    # Traemos también el ÁREA y ordenamos por ella
    query = """
        SELECT t.id, c.nombre as casa, a.nombre as area, i.nombre as item, t.descripcion as detalles, t.estado
        FROM obras_tarea t
        JOIN maestro_items i ON t.item_id = i.id
        JOIN maestro_areas a ON t.area_id = a.id
        JOIN casas_general c ON t.casa_id = c.id
        WHERE t.casa_id = %s
        ORDER BY a.nombre, t.created_at DESC
    """
    df_tickets = logic.db.run_query(query, (id_casa_actual,), return_data=True)

    if not df_tickets.empty:
        st.info(f"Editando tickets de: **{casa_seleccionada}**")

        # --- 3. FORMULARIO DE EDICIÓN (Solución al error) ---
        # El formulario congela la tabla para que no se recargue con cada clic
        with st.form("form_edicion_tickets"):
            
            df_editado = st.data_editor(
                df_tickets,
                column_order=("casa", "area", "item", "detalles", "estado"),
                column_config={
                    "id": None, # Oculto
                    "casa": st.column_config.TextColumn("Casa", disabled=True),
                    "area": st.column_config.TextColumn("Área", disabled=True),
                    "item": st.column_config.TextColumn("Item", disabled=True),
                    "detalles": st.column_config.TextColumn("Detalles / Observación", width="large"),
                    "estado": st.column_config.SelectboxColumn(
                        "Estado Actual",
                        options=["TIENE POSTVENTA", "POSTVENTA CORREGIDA", "OK", "PENDIENTE", "TERMINADO"], 
                        required=True,
                        width="medium"
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="editor_tickets"
            )

            # --- BOTÓN DE ENVÍO (Debe ser form_submit_button) ---
            submitted = st.form_submit_button("💾 Guardar Cambios", type="primary")

            if submitted:
                try:
                    cambios_detectados = 0
                    
                    for index, row in df_editado.iterrows():
                        # A. Buscamos el valor original usando el ID oculto
                        original_row = df_tickets[df_tickets['id'] == row['id']].iloc[0]
                        estado_original = original_row['estado']
                        detalle_original = original_row['detalles']
                        
                        # B. Detectamos cambios de ESTADO
                        if row['estado'] != estado_original:
                            # 1. Bitácora
                            logic.db.run_query("""
                                INSERT INTO obras_historial (tarea_id, estado_anterior, estado_nuevo, fecha_cambio)
                                VALUES (%s, %s, %s, NOW())
                            """, (int(row['id']), estado_original, row['estado']))
                            
                            # 2. Actualización
                            logic.db.run_query("""
                                UPDATE obras_tarea
                                SET estado = %s, descripcion = %s, updated_at = NOW()
                                WHERE id = %s
                            """, (row['estado'], row['detalles'], int(row['id'])))
                            
                            cambios_detectados += 1
                        
                        # C. Detectamos cambios solo de DETALLE (sin cambio de estado)
                        elif row['detalles'] != detalle_original:
                            logic.db.run_query("""
                                UPDATE obras_tarea SET descripcion = %s WHERE id = %s
                            """, (row['detalles'], int(row['id'])))

                    if cambios_detectados > 0:
                        st.success(f"✅ Se registraron {cambios_detectados} cambios de estado.")
                    else:
                        st.success("✅ Datos guardados correctamente.")
                    
                    time.sleep(1)
                    st.rerun() 
                    
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    else:
        st.warning(f"La casa **{casa_seleccionada}** no tiene tickets registrados aún.")