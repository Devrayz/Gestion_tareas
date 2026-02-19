import streamlit as st #type: ignore
# Importamos las vistas desde la carpeta views
from views import manual, grid, kpi, importador, historial, master, balance, matriz





# Configuración Global
st.set_page_config(page_title="Panel Maestro Foresta", layout="wide", page_icon="🏗️")
st.markdown("<style>.block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

def main():
    st.title("🏗️ Centro de Comando - FOresta Etapa 1")

    # Creamos las pestañas
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8= st.tabs([
        "➕ Registro (WhatsApp)", 
        "📝 Edición (Grid)", 
        "📊 Dashboard KPI",
        "📈 Balance Semanal", 
        "📜 Historial Comité",
        "📂 Importar CSV",
        "🚀 Importador Maestro",
        "🏢 Matriz General de Estado"
    ])

    # Llamamos a cada archivo por separado
    with tab1:
        manual.render_view()
    
    with tab2:
        grid.render_view()
        
    with tab3:
        kpi.render_view()
    with tab4: 
        balance.render_view()
        
    with tab5:
        historial.render_view()

    with tab6: 
        importador.render_view()

    with tab7: 
        master.render_view()
    with tab8: 
        matriz.render_view()

if __name__ == "__main__":
    main()