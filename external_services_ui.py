"""
Mr.Holmes External Services UI Component - Interface para serviços externos
Componente pronto para integrar ao Streamlit
"""

import streamlit as st
from external_services import get_services_by_category, get_categories

def display_external_services():
    """
    Exibe a interface de serviços externos categorizados
    Integre esta função em seu web_app.py
    """
    
    st.markdown("---")
    st.markdown("""
    <div class='mh-page'>
        <span class='eyebrow'>🔧 Ferramentas Externas</span>
        <h1>OSINT - Serviços Complementares</h1>
        <p class='desc'>Acesso direto a plataformas especializadas de busca e investigação</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Tabs para organizar as categorias
    categories = get_categories()
    tabs = st.tabs(categories)
    
    services_by_category = get_services_by_category()
    
    for tab, category in zip(tabs, categories):
        with tab:
            category_data = services_by_category[category]
            
            # Descrição da categoria
            st.info(f"📌 {category_data['description']}")
            
            # Grid de serviços
            services = category_data.get("services", [])
            
            # Criar colunas (2 por linha)
            cols = st.columns(2, gap="medium")
            
            for idx, service in enumerate(services):
                col = cols[idx % 2]
                
                with col:
                    # Card do serviço
                    st.markdown(f"""
                    <div style='
                        border: 1px solid #334355;
                        border-radius: 8px;
                        padding: 1rem;
                        background: linear-gradient(135deg, #1b232d 0%, #151c25 100%);
                        height: 180px;
                        display: flex;
                        flex-direction: column;
                        justify-content: space-between;
                    '>
                        <div>
                            <h3 style='margin: 0 0 0.5rem 0; color: #6fd4be;'>
                                {service['icon']} {service['name']}
                            </h3>
                            <p style='margin: 0; color: #9aa7b7; font-size: 0.9rem;'>
                                {service['description']}
                            </p>
                        </div>
                        <div style='margin-top: 1rem;'>
                            <a href='{service['url']}' target='_blank' style='
                                display: inline-block;
                                background: #6fd4be;
                                color: #11161d;
                                padding: 0.6rem 1.2rem;
                                border-radius: 6px;
                                text-decoration: none;
                                font-weight: 600;
                                font-size: 0.9rem;
                            '>
                                Acessar →
                            </a>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

def display_services_grid():
    """
    Exibe os serviços em um grid sem categorias (alternativa)
    """
    
    st.markdown("---")
    st.markdown("""
    <div class='mh-page'>
        <span class='eyebrow'>🔧 Ferramentas Externas</span>
        <h1>OSINT - Serviços Complementares</h1>
        <p class='desc'>Acesso direto a plataformas especializadas de busca e investigação</p>
    </div>
    """, unsafe_allow_html=True)
    
    from external_services import get_all_services_flat
    
    services = get_all_services_flat()
    
    # Grid responsivo - 3 colunas
    cols = st.columns(3, gap="medium")
    
    for idx, service in enumerate(services):
        col = cols[idx % 3]
        
        with col:
            st.markdown(f"""
            <div style='
                border: 1px solid #334355;
                border-radius: 8px;
                padding: 1.2rem;
                background: linear-gradient(135deg, #1b232d 0%, #151c25 100%);
                height: 200px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            '>
                <div>
                    <h3 style='margin: 0 0 0.3rem 0; color: #6fd4be; font-size: 1.1rem;'>
                        {service['icon']} {service['name']}
                    </h3>
                    <p style='margin: 0 0 0.5rem 0; color: #9aa7b7; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em;'>
                        {service['category']}
                    </p>
                    <p style='margin: 0; color: #c5ced9; font-size: 0.85rem; line-height: 1.4;'>
                        {service['description']}
                    </p>
                </div>
                <div style='margin-top: 1rem;'>
                    <a href='{service['url']}' target='_blank' style='
                        display: inline-block;
                        background: linear-gradient(135deg, #6fd4be 0%, #4fc4ab 100%);
                        color: #0d1218;
                        padding: 0.6rem 1rem;
                        border-radius: 6px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 0.85rem;
                        width: 100%;
                        text-align: center;
                        box-sizing: border-box;
                    '>
                        Acessar →
                    </a>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ────────────────────────────────────────────────────────────────────────────────
# INSTRUÇÕES DE INTEGRAÇÃO
# ────────────────────────────────────────────────────────────────────────────────
"""
COMO INTEGRAR NO web_app.py:

1. Adicione estas linhas no topo do arquivo:
   from external_services_ui import display_external_services, display_services_grid

2. No final do arquivo, antes de fechar o main():
   # Opção A: Com abas por categoria
   display_external_services()
   
   # Opção B: Grid simples sem categorias
   # display_services_grid()

3. Salve e recarregue seu aplicativo Streamlit!

CUSTOMIZAÇÃO:
- Para adicionar/remover serviços, edite o arquivo: external_services.py
- Para mudar cores, edite as variáveis CSS em web_app.py
- Para alterar layout, modifique os st.columns() nestas funções
"""
