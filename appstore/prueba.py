import auth
import database as db
import streamlit as st

# Datos del Admin
email_admin = "trocha0125@gmail.com"
nombre_admin = "Admin Principal"
clave_admin = "jaerroot" # La que usarás para loguearte

try:
    # 1. Hashear la clave usando la función que acabamos de agregar
    password_encriptada = auth.hash_password(clave_admin)
    
    # 2. Insertar en Postgres (fíjate en los %s)
    query = """
    INSERT INTO usuarios (nombre_completo,email, password_hash, rol, activo) 
    VALUES (%s, %s, %s, %s,%s)
    ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash;
    """
    
    db.run_query(query, (nombre_admin, email_admin, 'Admin', password_encriptada,'true'))
    print(f"✅ Usuario {email_admin} creado/actualizado correctamente.")

except Exception as e:
    print(f"❌ Error al crear usuario: {e}")