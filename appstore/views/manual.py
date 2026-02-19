import streamlit as st
import logic
import time

def render_view():
    st.header("⚡ Captura Inteligente de Tickets")
    
    # --- 1. CARGA SEGURA DE DATOS (FUERA DEL FORMULARIO) ---
    # Esto evita el error "Missing Submit Button" si falla la BD
    try:
        df_casas = logic.db.run_query("SELECT id, nombre FROM casas_general ORDER BY id", return_data=True)
        df_areas = logic.db.run_query("SELECT id, nombre FROM maestro_areas ORDER BY nombre", return_data=True)
        df_items = logic.db.run_query("SELECT id, nombre FROM maestro_items ORDER BY nombre", return_data=True)
    except Exception as e:
        st.error("⚠️ La conexión a la base de datos se cerró. Por favor recarga la página.")
        if st.button("🔄 Reconectar"):
            st.rerun()
        return # Detenemos la ejecución aquí para no dibujar un formulario roto

    # Si llegamos aquí, la BD está viva y tenemos datos
    dict_casas = dict(zip(df_casas['nombre'], df_casas['id']))
    dict_areas = dict(zip(df_areas['nombre'], df_areas['id']))
    dict_items = dict(zip(df_items['nombre'], df_items['id']))

    # --- GESTIÓN DE MEMORIA ---
    if "conflicto_detectado" not in st.session_state:
        st.session_state.conflicto_detectado = None
    if "datos_pendientes" not in st.session_state:
        st.session_state.datos_pendientes = {}

    c_form, c_info = st.columns([2, 1])
    
    with c_form:
        contenedor_form = st.container()

        # 2. FORMULARIO DE CAPTURA
        if st.session_state.conflicto_detectado is None:
            with contenedor_form.form("form_alta_rapida"):
                st.caption("Ingresa el reporte. El sistema detectará si es un duplicado.")
                
                col_a, col_b = st.columns(2)
                sel_casa = col_a.selectbox("🏡 Casa", list(dict_casas.keys()))
                sel_area = col_a.selectbox("📍 Área", list(dict_areas.keys()))
                sel_item = col_b.selectbox("🔧 Item", list(dict_items.keys()))
                
                sel_estado = col_b.selectbox("Estado", ["TIENE POSTVENTA", "POSTVENTA CORREGIDA", "OK"])
                descripcion = st.text_area("📝 Detalle / Observación", height=80)
                
                # EL BOTÓN AHORA SIEMPRE SE DIBUJARÁ
                submitted = st.form_submit_button("Guardar Ticket", type="primary")

                if submitted:
                    if descripcion:
                        try:
                            # Preparamos IDs
                            id_casa = int(dict_casas[sel_casa])
                            id_area = int(dict_areas[sel_area])
                            id_item = int(dict_items[sel_item])
                            
                            # 2.1 EL DETECTIVE: ¿Ya existe esto?
                            query_check = """
                                SELECT id, estado, descripcion, created_at FROM obras_tarea 
                                WHERE casa_id = %s AND area_id = %s AND item_id = %s
                                ORDER BY created_at DESC LIMIT 1
                            """
                            existente = logic.db.run_query(query_check, (id_casa, id_area, id_item), return_data=True)

                            datos_nuevos = {
                                "nombre": f"{sel_item} en {sel_area}",
                                "desc": descripcion,
                                "estado": sel_estado,
                                "ids": (id_casa, id_area, id_item)
                            }

                            if not existente.empty:
                                fila = existente.iloc[0]
                                st.session_state.conflicto_detectado = {
                                    "id_tarea": int(fila['id']),
                                    "estado_viejo": fila['estado'],
                                    "estado_nuevo": sel_estado,
                                    "desc_vieja": fila['descripcion'],
                                    "fecha_origen": fila['created_at']
                                }
                                st.session_state.datos_pendientes = datos_nuevos
                                st.rerun()
                                
                            else:
                                # 2.2 INSERTAR NUEVO
                                res = logic.db.run_query("""
                                    INSERT INTO obras_tarea (nombre, descripcion, estado, casa_id, area_id, item_id, es_postventa, created_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW()) RETURNING id;
                                """, (datos_nuevos['nombre'], datos_nuevos['desc'], datos_nuevos['estado'], *datos_nuevos['ids']), return_data=True)
                                
                                nueva_id = int(res.iloc[0]['id'])
                                
                                # 2.3 HISTORIAL
                                logic.db.run_query("""
                                    INSERT INTO obras_historial (tarea_id, estado_anterior, estado_nuevo, fecha_cambio)
                                    VALUES (%s, 'NUEVO', %s, NOW())
                                """, (nueva_id, datos_nuevos['estado']))
                                
                                st.success("✅ Ticket Nuevo creado exitosamente.")

                        except Exception as e:
                            # Aquí capturamos si la conexión se cae AL MOMENTO DE GUARDAR
                            st.error(f"Error guardando: {e}")
                            st.info("Intenta presionar el botón de nuevo.")
                    else:
                        st.warning("⚠️ Falta la descripción.")

        # 3. PANTALLA DE CONFLICTO (Duplicados)
        else:
            conflicto = st.session_state.conflicto_detectado
            nuevos = st.session_state.datos_pendientes
            
            st.warning("🚨 **TAREA YA EXISTENTE**")
            st.write(f"Este ticket ya fue creado el: **{conflicto['fecha_origen']}**")
            
            c1, c2 = st.columns(2)
            c1.info(f"**Anterior:** {conflicto['estado_viejo']}")
            c2.success(f"**Nuevo:** {nuevos['estado']}")
            
            st.markdown(f"**¿Qué quieres hacer?**")
            
            col_btn1, col_btn2 = st.columns(2)

            if col_btn1.button("🔄 ACTUALIZAR (Reemplazar estado)", type="primary"):
                try:
                    # Actualizar tarea
                    logic.db.run_query("""
                        UPDATE obras_tarea 
                        SET estado = %s, descripcion = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (nuevos['estado'], nuevos['desc'], conflicto['id_tarea']))
                    
                    # Historial
                    logic.db.run_query("""
                        INSERT INTO obras_historial (tarea_id, estado_anterior, estado_nuevo, fecha_cambio)
                        VALUES (%s, %s, %s, NOW())
                    """, (int(conflicto['id_tarea']), conflicto['estado_viejo'], nuevos['estado']))
                    
                    st.success("✅ Ticket actualizado.")
                    st.session_state.conflicto_detectado = None
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar: {e}")

            if col_btn2.button("🔙 Cancelar"):
                st.session_state.conflicto_detectado = None
                st.rerun()

    # --- PANEL LATERAL ---
    with c_info:
        st.info("💡 **Bitácora Activa**")
        st.subheader("🕒 Recientes")
        try:
            ultimos = logic.db.run_query("""
                SELECT c.nombre as Casa, t.nombre as Tarea, t.estado 
                FROM obras_tarea t JOIN casas_general c ON t.casa_id = c.id
                ORDER BY t.created_at DESC LIMIT 5
            """, return_data=True)
            if ultimos is not None:
                st.dataframe(ultimos, hide_index=True)
        except: pass