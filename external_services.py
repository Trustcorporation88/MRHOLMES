"""
Mr.Holmes — catálogo de serviços externos OSINT, separados por categoria.
Cada serviço fica apenas na categoria correspondente.
"""

# page_key liga a categoria às páginas do web_app (Telefone, Domínio, etc.)
EXTERNAL_SERVICES = {
    "pessoas": {
        "label": "Busca de Pessoas",
        "icon": "🧠",
        "description": "Investigação de indivíduos e perfis públicos",
        "page_keys": ["pessoas", "email", "osint"],
        "services": [
            {
                "id": "mind",
                "name": "Mind Search",
                "url": "https://mind-7.org/?r=fala_melo",
                "icon": "🧠",
                "description": "Busca avançada de informações pessoais em fontes abertas",
                "use_for": "Nome, CPF/documento, perfil e investigação de pessoas",
            },
        ],
    },
    "telefone": {
        "label": "Telefone",
        "icon": "📱",
        "description": "Consulta reversa de números e contatos",
        "page_keys": ["telefone"],
        "services": [
            {
                "id": "syncme",
                "name": "Sync.me",
                "url": "https://sync.me/pt-br/",
                "icon": "📱",
                "description": "Identificação de dono de telefone e agenda reversa",
                "use_for": "Número de celular / WhatsApp / caller ID",
            },
        ],
    },
    "leaks": {
        "label": "Leaks e Vazamentos",
        "icon": "🔓",
        "description": "Bases de dados expostas e breaches",
        "page_keys": ["leaks", "email"],
        "services": [
            {
                "id": "dehashed",
                "name": "Dehashed",
                "url": "https://www.dehashed.com/",
                "icon": "🔓",
                "description": "Busca em dumps e violações de credenciais",
                "use_for": "Email, username, senha vazada, domínio em breach",
            },
        ],
    },
    "dominio": {
        "label": "Domínio e Website",
        "icon": "🕸️",
        "description": "Análise técnica de sites e infraestrutura",
        "page_keys": ["dominio", "rede"],
        "services": [
            {
                "id": "webcheck",
                "name": "Web-Check",
                "url": "https://web-check.xyz/",
                "icon": "🕸️",
                "description": "SSL, DNS, headers, tecnologias e fingerprint do site",
                "use_for": "Domínio, URL, stack e postura do website",
            },
        ],
    },
    "imagem": {
        "label": "Imagem e Metadados",
        "icon": "🖼️",
        "description": "EXIF e metadados de arquivos de imagem",
        "page_keys": ["imagem", "osint"],
        "services": [
            {
                "id": "jimpl",
                "name": "Jimpl",
                "url": "https://jimpl.com/",
                "icon": "🖼️",
                "description": "Leitura de EXIF/metadados de fotos (GPS, câmera, software)",
                "use_for": "Foto, imagem JPEG/PNG e metadados embutidos",
            },
        ],
    },
}


def get_categories():
    """Lista ordenada de chaves de categoria."""
    return list(EXTERNAL_SERVICES.keys())


def get_category(category_key):
    """Retorna uma categoria pelo id interno (pessoas, telefone, ...)."""
    return EXTERNAL_SERVICES.get(category_key)


def get_all_categories():
    """Todas as categorias com dados completos."""
    return EXTERNAL_SERVICES


def get_services_for_page(page_key):
    """
    Serviços cujo page_keys inclui a página atual.
    page_key exemplos: telefone, dominio, leaks, email, pessoas, imagem
    """
    key = (page_key or "").strip().lower()
    blocks = []
    for cat_key, cat in EXTERNAL_SERVICES.items():
        if key in [k.lower() for k in cat.get("page_keys", [])] or key == cat_key:
            blocks.append((cat_key, cat))
    return blocks


def get_all_services_flat():
    """Lista plana com category_key e category_label em cada serviço."""
    out = []
    for cat_key, cat in EXTERNAL_SERVICES.items():
        for svc in cat.get("services", []):
            item = dict(svc)
            item["category_key"] = cat_key
            item["category_label"] = cat["label"]
            item["category_icon"] = cat["icon"]
            out.append(item)
    return out
