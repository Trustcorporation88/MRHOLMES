"""
Mr.Holmes External OSINT Services - Integração de Serviços Externos
Categoria de serviços OSINT categorizados com links e redirecionamentos
"""

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

def get_services_by_category(category=None):
    """
    Retorna serviços filtrados por categoria
    
    Args:
        category (str, optional): Nome da categoria. Se None, retorna todas.
    
    Returns:
        dict: Serviços organizados por categoria
    """
    if category:
        return {category: EXTERNAL_SERVICES.get(category, {})}
    return EXTERNAL_SERVICES

def get_all_services_flat():
    """
    Retorna todos os serviços em uma lista única (sem categorias)
    
    Returns:
        list: Lista com todos os serviços
    """
    all_services = []
    for category, data in EXTERNAL_SERVICES.items():
        for service in data.get("services", []):
            service["category"] = category
            all_services.append(service)
    return all_services

def get_service_by_type(service_type):
    """
    Retorna serviços filtrados por tipo
    
    Args:
        service_type (str): Tipo de serviço (people_search, database_search, etc)
    
    Returns:
        list: Lista de serviços do tipo especificado
    """
    matching_services = []
    for category, data in EXTERNAL_SERVICES.items():
        for service in data.get("services", []):
            if service.get("type") == service_type:
                service["category"] = category
                matching_services.append(service)
    return matching_services

def get_categories():
    """
    Retorna lista de categorias disponíveis
    
    Returns:
        list: Lista de categorias
    """
    return list(EXTERNAL_SERVICES.keys())
