import psycopg2
import pandas as pd
import streamlit as st

def get_connection():
    # Usa exactamente los nombres que pusiste en secrets.toml
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        database=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"]
    )

def run_query(query, params=(), return_data=False):
    conn = get_connection()
    try:
        if return_data:
            return pd.read_sql_query(query, conn, params=params)
        else:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
    finally:
        conn.close()

def init_db():
    """Solo verifica que la conexión a Postgres esté activa."""
    try:
        conn = get_connection()
        conn.close()
    except Exception as e:
        st.error(f"Error de conexión inicial: {e}")