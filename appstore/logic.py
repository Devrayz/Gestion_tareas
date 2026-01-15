import streamlit as st
import database as db
import pandas as pd
import auth 

def view_admin_dashboard():
    st.title("📊 Panel de Control (Admin)")
    
    # ---------------------------------------------------------
    # 1. CARGA DE DATOS "INTELIGENTE" (CON JOINS)
    # ---------------------------------------------------------
    # Unimos: obras_tarea + casas_general + usuarios
    query_master = """
        SELECT 
            t.id, 
            t.nombre as tarea, 
            t.descripcion, 
            t.estado, 
            t.created_at,
            c.nombre as proyecto, 
            u.nombre_completo as responsable,
            t.casa_id,        -- Los traemos ocultos para filtros
            t.asignado_a_id
        FROM obras_tarea t
        LEFT JOIN casas_general c ON t.casa_id = c.id
        LEFT JOIN usuarios u ON t.asignado_a_id = u.id
        ORDER BY t.created_at DESC
    """
    df_all = db.run_query(query_master, return_data=True)
    
    if df_all is None or df_all.empty:
        st.info("No hay tareas registradas.")
        # Estructura vacía para evitar errores
        df_all = pd.DataFrame(columns=['id', 'tarea', 'descripcion', 'estado', 'proyecto', 'responsable'])

    # ---------------------------------------------------------
    # 2. SECCIÓN DE FILTROS (Basados en Nombres, no IDs)
    # ---------------------------------------------------------
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            # Filtro por Proyecto (Nombre real)
            lista_proyectos = ["Todos"] + sorted(list(df_all['proyecto'].dropna().unique()))
            f_proyecto = st.selectbox("📂 Proyecto / Casa", lista_proyectos)
        with c2:
            # Filtro por Responsable (Nombre real)
            lista_resp = ["Todos"] + sorted(list(df_all['responsable'].dropna().unique()))
            f_resp = st.selectbox("👷 Responsable", lista_resp)
        with c3:
            lista_est = ["Todos"] + sorted(list(df_all['estado'].unique())) if 'estado' in df_all.columns else ["Todos"]
            f_estado = st.selectbox("🚦 Estado", lista_est)

    # Aplicar Filtros
    df_view = df_all.copy()
    if f_proyecto != "Todos": df_view = df_view[df_view['proyecto'] == f_proyecto]
    if f_resp != "Todos": df_view = df_view[df_view['responsable'] == f_resp]
    if f_estado != "Todos": df_view = df_view[df_view['estado'] == f_estado]

    # ---------------------------------------------------------
    # 3. VISUALIZACIÓN DE DATOS
    # ---------------------------------------------------------
    # Métricas
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Tareas", len(df_view))
    if 'estado' in df_view.columns:
        m2.metric("Pendientes", len(df_view[df_view['estado']=='Pendiente']))
        m3.metric("Terminadas", len(df_view[df_view['estado']=='Terminado']))

    # Tabla Principal (Ocultamos IDs técnicos)
    st.dataframe(
        df_view[['id', 'tarea', 'proyecto', 'responsable', 'estado', 'descripcion']], 
        use_container_width=True, 
        hide_index=True
    )

    st.divider()

    # =========================================================
    # 4. GESTIÓN ADMINISTRATIVA (Pestañas para ordenar)
    # =========================================================
    tab_casas, tab_tareas, tab_usuarios = st.tabs(["🏗️ Gestión Proyectos", "➕ Asignar Tarea", "👤 Usuarios"])

    # --- PESTAÑA A: CREAR NUEVA CASA / PROYECTO ---
    with tab_casas:
        st.subheader("Registrar Nuevo Proyecto")
        with st.form("form_new_house"):
            c_h1, c_h2 = st.columns(2)
            with c_h1:
                h_nombre = st.text_input("Nombre del Proyecto (ej. Casa Lote 4)")
                h_dir = st.text_input("Dirección / Ubicación")
            with c_h2:
                h_etapa = st.selectbox("Etapa Actual", ["Cimentación", "Obra Negra", "Acabados", "Entregada", "Postventa"])
                h_entrega = st.date_input("Fecha Estimada Entrega")
            
            if st.form_submit_button("Guardar Proyecto"):
                if h_nombre:
                    try:
                        db.run_query(
                            "INSERT INTO casas_general (nombre, direccion, etapa_proyecto, fecha_entrega) VALUES (%s, %s, %s, %s)",
                            (h_nombre, h_dir, h_etapa, h_entrega)
                        )
                        st.success(f"Proyecto '{h_nombre}' creado exitosamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear casa: {e}")
                else:
                    st.warning("El nombre es obligatorio.")

    
    # --- PESTAÑA B: ASIGNAR TAREA (Completo con Dependencias) ---
    with tab_tareas:
        with st.form("admin_task_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                t_nombre = st.text_input("Título de la Tarea")
                t_desc = st.text_area("Detalles")
            with col_b:
                # 1. Selector de Casas Reales
                casas_db = db.run_query("SELECT id, nombre FROM casas_general WHERE es_entregada=FALSE ORDER BY nombre", return_data=True)
                opciones_casas = {row['nombre']: row['id'] for _, row in casas_db.iterrows()} if not casas_db.empty else {}
                sel_casa_nombre = st.selectbox("Proyecto", list(opciones_casas.keys()) if opciones_casas else ["Sin Proyectos"])
                
                # 2. Selector de Responsables Reales
                users_db = db.run_query("SELECT id, nombre_completo FROM usuarios WHERE activo=TRUE", return_data=True)
                opciones_users = {row['nombre_completo']: row['id'] for _, row in users_db.iterrows()} if not users_db.empty else {}
                sel_user_nombre = st.selectbox("Asignar a", list(opciones_users.keys()) if opciones_users else ["Sin Usuarios"])

            # 3. [NUEVO] Selector de Dependencia para el Admin
            # Traemos todas las tareas para que el Admin pueda conectar cualquiera
            all_tasks = db.run_query("SELECT id, nombre FROM obras_tarea", return_data=True)
            opciones_dep = [None] + list(all_tasks['id']) if not all_tasks.empty else [None]
            # Usamos un format_func para que se vea bonito en el selector
            t_dep_id = st.selectbox("¿Depende de otra tarea previa?", opciones_dep, format_func=lambda x: f"ID {x}" if x else "Ninguna")

            if st.form_submit_button("Crear Tarea"):
                if opciones_casas and opciones_users and t_nombre:
                    real_casa_id = opciones_casas[sel_casa_nombre]
                    real_user_id = opciones_users[sel_user_nombre]
                    
                    # --- LÓGICA CLAVE AQUÍ ---
                    # Si eligió una dependencia, nace Bloqueada. Si no, Pendiente.
                    estado_inicial = "Bloqueado" if t_dep_id else "Pendiente"
                    
                    db.run_query(
                        """INSERT INTO obras_tarea 
                           (nombre, descripcion, estado, casa_id, asignado_a_id, tarea_previa_id, created_at) 
                           VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
                        (t_nombre, t_desc, estado_inicial, real_casa_id, real_user_id, t_dep_id)
                    )
                    st.success(f"Tarea asignada (Estado: {estado_inicial})")
                    st.rerun()
                else:
                    st.error("Faltan datos o no hay proyectos/usuarios registrados.")

    # --- PESTAÑA C: CREAR USUARIOS ---
    with tab_usuarios:
        with st.form("new_user_form"):
            u_email = st.text_input("Correo").lower().strip()
            u_nombre = st.text_input("Nombre Completo")
            u_rol = st.selectbox("Rol", ["Operario", "Admin"])
            u_pass = st.text_input("Contraseña", type="password")
            u_activo = st.checkbox("Usuario Activo", value=True)

            if st.form_submit_button("Crear Usuario"):
                if u_email and u_pass:
                    h_pass = auth.hash_password(u_pass)
                    try:
                        db.run_query(
                            "INSERT INTO usuarios (nombre_completo, email, password_hash, rol, activo) VALUES (%s, %s, %s, %s, %s)",
                            (u_nombre, u_email, h_pass, u_rol, u_activo)
                        )
                        st.success(f"Usuario {u_nombre} creado.")
                    except Exception as e:
                        st.error(f"Error: {e}")

def view_operario_dashboard(usuario_email):
    st.title(f"👷 Mi Agenda")
    
    # Obtener ID del usuario
    user_data = db.run_query("SELECT id FROM usuarios WHERE email=%s", (usuario_email,), return_data=True)
    if user_data.empty:
        st.error("Usuario no encontrado.")
        return
    usuario_id = int(user_data.iloc[0]['id'])

    tab1, tab2 = st.tabs(["📋 Mis Pendientes", "➕ Reportar Actividad"])
    
    # --- PESTAÑA 1: VISUALIZACIÓN CON NOMBRES REALES ---
    # --- PESTAÑA 1: VISUALIZACIÓN CON NOMBRES REALES ---
    with tab1:
        q_operario = """
            SELECT t.*, c.nombre as nombre_casa 
            FROM obras_tarea t
            LEFT JOIN casas_general c ON t.casa_id = c.id
            WHERE t.asignado_a_id = %s
            ORDER BY t.estado DESC, t.created_at DESC
        """
        mis_tareas = db.run_query(q_operario, (usuario_id,), return_data=True)
        
        if mis_tareas is None or mis_tareas.empty:
            st.info("No tienes tareas pendientes.")
        else:
            cols = st.columns(2)
            # CORRECCIÓN AQUÍ: Usamos enumerate para obtener 'i' seguro
            for i, (index, row) in enumerate(mis_tareas.iterrows()):
                with cols[i % 2]:
                    with st.container(border=True):
                        icon = "✅" if row['estado']=='Terminado' else "🚧" if row['estado']=='En Progreso' else "⏳"
                        
                        st.subheader(f"{icon} {row['nombre']}")
                        # Manejo seguro si nombre_casa viene vacío
                        nom_casa = row['nombre_casa'] if row['nombre_casa'] else "Sin Proyecto"
                        st.caption(f"📍 Proyecto: **{nom_casa}**") 
                        st.write(row['descripcion'])
                        
                        # --- Lógica de Bloqueo Visual ---
                        bloqueado = False
                        if row['tarea_previa_id']:
                            padre = db.run_query("SELECT estado, nombre FROM obras_tarea WHERE id=%s", (row['tarea_previa_id'],), return_data=True)
                            if not padre.empty and padre.iloc[0]['estado'] != "Terminado":
                                bloqueado = True
                                st.error(f"⛔ Bloqueado por: {padre.iloc[0]['nombre']}")

                        if not bloqueado:
                            estados = ["Pendiente", "En Progreso", "Terminado"]
                            # Buscamos índice seguro
                            idx = estados.index(row['estado']) if row['estado'] in estados else 0
                            
                            # Key única agregando _{i}
                            nuevo_est = st.selectbox("Estado", estados, index=idx, key=f"st_{row['id']}_{i}")
                            
                            if nuevo_est != row['estado']:
                                # CORRECCIÓN EN EL KEY DEL BOTÓN: Agregamos _{i}
                                if st.button("Actualizar", key=f"btn_{row['id']}_{i}", use_container_width=True):
                                    # 1. Update tarea actual
                                    db.run_query("UPDATE obras_tarea SET estado=%s WHERE id=%s", (nuevo_est, row['id']))
                                    
                                    # 2. Desbloqueo en cadena
                                    if nuevo_est == "Terminado":
                                        db.run_query("UPDATE obras_tarea SET estado='Pendiente' WHERE tarea_previa_id=%s AND estado='Bloqueado'", (row['id'],))
                                    
                                    st.success("Actualizado")
                                    st.rerun()
                        else:
                            st.info("Debes esperar a que se termine la tarea anterior.")

    # --- PESTAÑA 2: CREAR TAREA (Solo casas existentes) ---
    with tab2:
        st.subheader("Reportar nueva tarea")
        with st.form("op_create"):
            op_nombre = st.text_input("¿Qué hay que hacer?")
            op_desc = st.text_area("Detalles adicionales")
            
            # Selector de Casas (Solo las existentes)
            casas_db = db.run_query("SELECT id, nombre FROM casas_general WHERE es_entregada=FALSE", return_data=True)
            mapa_casas = {row['nombre']: row['id'] for _, row in casas_db.iterrows()} if not casas_db.empty else {}
            
            sel_casa = st.selectbox("Ubicación", list(mapa_casas.keys()) if mapa_casas else ["Sin Proyectos"])
            
            if st.form_submit_button("Crear Reporte"):
                if mapa_casas and op_nombre:
                    real_casa_id = mapa_casas[sel_casa]
                    db.run_query(
                        "INSERT INTO obras_tarea (nombre, descripcion, estado, casa_id, asignado_a_id, created_at) VALUES (%s, %s, 'Pendiente', %s, %s, NOW())",
                        (op_nombre, op_desc, real_casa_id, usuario_id)
                    )
                    st.success("Reporte creado.")
                    st.rerun()
                else:
                    st.error("Información incompleta.")