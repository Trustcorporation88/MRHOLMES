"""
EXEMPLO DE INTEGRAÇÃO DOS SERVIÇOS EXTERNOS NO web_app.py

Este arquivo mostra exatamente onde e como adicionar os serviços externos
ao seu aplicativo Streamlit Mr.Holmes
"""

# ════════════════════════════════════════════════════════════════════════════════
# PASSO 1: Adicione este import no TOPO do seu web_app.py (após os outros imports)
# ════════════════════════════════════════════════════════════════════════════════

# import sys
# import os
# sys.path.insert(0, os.path.dirname(__file__))
# import streamlit as st
# from external_services_ui import display_external_services  # ← ADICIONE ESTA LINHA

# ════════════════════════════════════════════════════════════════════════════════
# PASSO 2: Localize a função main() ou a estrutura principal do seu app
# ════════════════════════════════════════════════════════════════════════════════

def main():
    """Função principal do aplicativo"""
    
    # ... todo o seu código existente ...
    
    # PASSO 3: No FINAL da função main(), antes do if __name__ == "__main__"
    # Adicione esta seção:
    
    # ────────────────────────────────────────────────────────────────────────────
    # SERVIÇOS EXTERNOS OSINT
    # ────────────────────────────────────────────────────────────────────────────
    if st.sidebar.checkbox("🔧 Mostrar Serviços Externos", value=True):
        display_external_services()
    
    # ────────────────────────────────────────────────────────────────────────────

# ════════════════════════════════════════════════════════════════════════════════
# VARIAÇÕES E ALTERNATIVAS
# ════════════════════════════════════════════════════════════════════════════════

# OPÇÃO 1: Mostrar sempre (sem checkbox)
# display_external_services()

# OPÇÃO 2: Mostrar em uma página separada (página multi-página do Streamlit)
# Crie uma pasta 'pages/' na raiz do projeto e adicione um arquivo 'pages/external_services.py'
# Conteúdo do 'pages/external_services.py':
"""
import streamlit as st
from external_services_ui import display_external_services

st.set_page_config(page_title="Serviços Externos", page_icon="🔧")
display_external_services()
"""

# OPÇÃO 3: Customizar as categorias mostradas
# from external_services import get_services_by_category
# st.write(get_services_by_category("🔍 Busca de Pessoas"))

# ════════════════════════════════════════════════════════════════════════════════
# ESTRUTURA COMPLETA EXEMPLO
# ════════════════════════════════════════════════════════════════════════════════

EXEMPLO_ESTRUTURA_COMPLETA = """
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from external_services_ui import display_external_services

st.set_page_config(
    page_title="Mr.Holmes",
    page_icon="🔎",
    layout="wide",
)

# ... CSS e design do seu app ...

def main():
    # ... sua lógica existente ...
    
    # Ferramentas principais
    tab1, tab2, tab3 = st.tabs(["Buscar Pessoa", "Buscar Domínio", "Análise"])
    
    with tab1:
        # ... seu código ...
        pass
    
    with tab2:
        # ... seu código ...
        pass
    
    with tab3:
        # ... seu código ...
        pass
    
    # Serviços externos
    with st.expander("🔧 Serviços Complementares"):
        display_external_services()

if __name__ == "__main__":
    main()
"""

# ════════════════════════════════════════════════════════════════════════════════
# ARQUIVO external_services.py - Estrutura dos dados
# ════════════════════════════════════════════════════════════════════════════════

EXTERNAL_SERVICES = {
    "🔍 Busca de Pessoas": {
        "description": "Ferramentas para buscar informações sobre indivíduos",
        "services": [
            {
                "name": "Mind Search",
                "url": "https://mind-7.org/?r=fala_melo",
                "icon": "🧠",
                "description": "Busca avançada de informações pessoais",
                "type": "people_search"
            },
            {
                "name": "Sync.me",
                "url": "https://sync.me/pt-br/",
                "icon": "👤",
                "description": "Banco de dados de pessoas e telefones",
                "type": "people_search"
            }
        ]
    },
    "🌐 Bases de Dados Expostas": {
        "description": "Verificar se dados pessoais foram vazados",
        "services": [
            {
                "name": "Dehashed",
                "url": "https://www.dehashed.com/",
                "icon": "🔓",
                "description": "Base de dados de leaks e violações de segurança",
                "type": "database_search"
            }
        ]
    },
    "🔗 Análise de Domínios": {
        "description": "Ferramentas para investigar websites e domínios",
        "services": [
            {
                "name": "Web-Check",
                "url": "https://web-check.xyz/",
                "icon": "🕸️",
                "description": "Análise completa de sites (SSL, DNS, tecnologias, etc)",
                "type": "domain_analysis"
            },
            {
                "name": "Jimpl",
                "url": "https://jimpl.com/",
                "icon": "🔎",
                "description": "Verificação de infraestrutura e tecnologias",
                "type": "domain_analysis"
            }
        ]
    }
}

# ════════════════════════════════════════════════════════════════════════════════
# PRÓXIMOS PASSOS
# ════════════════════════════════════════════════════════════════════════════════

PRÓXIMOS_PASSOS = """
1. ✅ Copie os dois arquivos criados para seu projeto:
   - external_services.py
   - external_services_ui.py

2. ✅ No seu web_app.py, adicione o import:
   from external_services_ui import display_external_services

3. ✅ Chame a função onde desejar mostrar os serviços:
   display_external_services()

4. ✅ Teste localmente:
   streamlit run web_app.py

5. ✅ Deploy no Railway:
   git add .
   git commit -m "feat: add external osint services"
   git push

6. ✅ (Opcional) Para adicionar mais serviços:
   - Edite external_services.py
   - Adicione novos serviços no dicionário EXTERNAL_SERVICES
   - Salve e recarregue
"""
