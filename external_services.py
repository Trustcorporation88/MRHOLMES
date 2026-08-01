"""
Mr.Holmes — catálogo de serviços externos OSINT, separados por categoria.
Inclui links originais + seleções OSINT do catálogo Z4nzu/hackingtool.
Cada serviço fica apenas na categoria correspondente.
"""

# page_key liga a categoria às páginas do web_app (Telefone, Domínio, etc.)
EXTERNAL_SERVICES = {
    "pessoas": {
        "label": "Busca de Pessoas",
        "icon": "🧠",
        "description": "Investigação de indivíduos, usernames e perfis públicos",
        "page_keys": ["pessoas", "email", "osint"],
        "services": [
            {
                "id": "mind",
                "name": "Mind Search",
                "url": "https://mind-7.org/?r=fala_melo",
                "icon": "🧠",
                "description": "Busca avançada de informações pessoais em fontes abertas",
                "use_for": "Nome, documento, perfil e investigação de pessoas",
                "source": "custom",
            },
            {
                "id": "sherlock",
                "name": "Sherlock",
                "url": "https://github.com/sherlock-project/sherlock",
                "icon": "🕵️",
                "description": "Username em centenas de redes sociais (hackingtool / OSINT)",
                "use_for": "Username / handle em redes",
                "source": "hackingtool",
            },
            {
                "id": "socialscan",
                "name": "SocialScan",
                "url": "https://github.com/iojw/socialscan",
                "icon": "👥",
                "description": "Checa disponibilidade de username ou email em plataformas",
                "use_for": "Username ou email em serviços online",
                "source": "hackingtool",
            },
            {
                "id": "osintframework",
                "name": "OSINT Framework",
                "url": "https://osintframework.com/",
                "icon": "🗺️",
                "description": "Mapa indexado de fontes e ferramentas OSINT",
                "use_for": "Descobrir fontes por tipo de dado",
                "source": "hackingtool",
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
                "source": "custom",
            },
        ],
    },
    "leaks": {
        "label": "Leaks e Vazamentos",
        "icon": "🔓",
        "description": "Bases de dados expostas, breaches e hashes",
        "page_keys": ["leaks", "email"],
        "services": [
            {
                "id": "dehashed",
                "name": "Dehashed",
                "url": "https://www.dehashed.com/",
                "icon": "🔓",
                "description": "Busca em dumps e violações de credenciais",
                "use_for": "Email, username, senha vazada, domínio em breach",
                "source": "custom",
            },
            {
                "id": "hibp",
                "name": "Have I Been Pwned",
                "url": "https://haveibeenpwned.com/",
                "icon": "📧",
                "description": "Verifica se email apareceu em breaches públicos",
                "use_for": "Email comprometido em vazamentos",
                "source": "hackingtool",
            },
            {
                "id": "crackstation",
                "name": "CrackStation",
                "url": "https://crackstation.net/",
                "icon": "🔑",
                "description": "Lookup online de hashes (referência forense)",
                "use_for": "Hash MD5/SHA em investigação autorizada",
                "source": "hackingtool",
            },
        ],
    },
    "dominio": {
        "label": "Domínio e Website",
        "icon": "🕸️",
        "description": "Análise técnica de sites, DNS e infraestrutura",
        "page_keys": ["dominio", "rede"],
        "services": [
            {
                "id": "webcheck",
                "name": "Web-Check",
                "url": "https://web-check.xyz/",
                "icon": "🕸️",
                "description": "SSL, DNS, headers, tecnologias e fingerprint do site",
                "use_for": "Domínio, URL, stack e postura do website",
                "source": "custom",
            },
            {
                "id": "crtsh",
                "name": "crt.sh",
                "url": "https://crt.sh/",
                "icon": "📜",
                "description": "Certificados SSL/TLS e subdomínios via CT logs",
                "use_for": "Subdomínios e histórico de certificados",
                "source": "hackingtool-adjacent",
            },
            {
                "id": "shodan",
                "name": "Shodan",
                "url": "https://www.shodan.io/",
                "icon": "🛰️",
                "description": "Busca de dispositivos e serviços expostos na internet",
                "use_for": "IP, banner, porta e superfície exposta",
                "source": "hackingtool",
            },
            {
                "id": "urlscan",
                "name": "urlscan.io",
                "url": "https://urlscan.io/",
                "icon": "🧪",
                "description": "Sandbox de URL com DOM, requests e screenshot",
                "use_for": "URL suspeita / phishing analysis defensivo",
                "source": "hackingtool-adjacent",
            },
            {
                "id": "viewdns",
                "name": "ViewDNS",
                "url": "https://viewdns.info/",
                "icon": "🔎",
                "description": "WHOIS, reverse IP, DNS history e lookups",
                "use_for": "Domínio, IP e histórico DNS",
                "source": "existing",
            },
        ],
    },
    "imagem": {
        "label": "Imagem e Metadados",
        "icon": "🖼️",
        "description": "EXIF, steganografia e análise de arquivos de imagem",
        "page_keys": ["imagem", "osint"],
        "services": [
            {
                "id": "jimpl",
                "name": "Jimpl",
                "url": "https://jimpl.com/",
                "icon": "🖼️",
                "description": "Leitura de EXIF/metadados de fotos (GPS, câmera, software)",
                "use_for": "Foto JPEG/PNG e metadados embutidos",
                "source": "custom",
            },
            {
                "id": "aperisolve",
                "name": "Aperi'Solve",
                "url": "https://www.aperisolve.com/",
                "icon": "🧩",
                "description": "Análise all-in-one de stego/metadados em imagem (hackingtool)",
                "use_for": "Steganografia e camadas ocultas em imagem",
                "source": "hackingtool",
            },
            {
                "id": "stegonline",
                "name": "StegOnline",
                "url": "https://georgeom.net/StegOnline/upload",
                "icon": "🔬",
                "description": "Explorador LSB de imagens no navegador",
                "use_for": "Bits ocultos / canais de cor em PNG/BMP",
                "source": "hackingtool",
            },
            {
                "id": "exiftool",
                "name": "ExifTool",
                "url": "https://exiftool.org/",
                "icon": "📋",
                "description": "Padrão da indústria para metadados de imagem/documento",
                "use_for": "EXIF, IPTC, XMP em foto e PDF",
                "source": "hackingtool",
            },
            {
                "id": "toolsley",
                "name": "Toolsley",
                "url": "https://www.toolsley.com/",
                "icon": "🛠️",
                "description": "Utilitários forenses online (file type, strings, etc.)",
                "use_for": "Arquivo binário / identificação rápida",
                "source": "hackingtool",
            },
        ],
    },
    "utilitarios": {
        "label": "Utilitários OSINT",
        "icon": "🧰",
        "description": "Decoders, referência e apoio à investigação",
        "page_keys": ["osint", "utilitarios"],
        "services": [
            {
                "id": "cyberchef",
                "name": "CyberChef",
                "url": "https://gchq.github.io/CyberChef/",
                "icon": "🍳",
                "description": "Canivete suíço de encode/decode/análise (hackingtool)",
                "use_for": "Base64, hex, JWT, regex, transformações",
                "source": "hackingtool",
            },
            {
                "id": "wigle",
                "name": "WiGLE",
                "url": "https://wigle.net/",
                "icon": "📡",
                "description": "Mapa mundial de redes Wi‑Fi (wardriving OSINT)",
                "use_for": "SSID, BSSID e geolocalização de Wi‑Fi",
                "source": "hackingtool",
            },
            {
                "id": "hackingtool",
                "name": "hackingtool (catálogo)",
                "url": "https://github.com/Z4nzu/hackingtool",
                "icon": "📦",
                "description": "215 ferramentas em 21 categorias — fonte desta curadoria OSINT",
                "use_for": "Descobrir ferramentas de recon (Linux/local)",
                "source": "hackingtool",
            },
        ],
    },
    "recon_cli": {
        "label": "Recon CLI (GitHub)",
        "icon": "⚙️",
        "description": "Ferramentas de linha de comando úteis em OSINT — links oficiais (não instala no site)",
        "page_keys": ["dominio", "osint", "rede"],
        "services": [
            {
                "id": "subfinder",
                "name": "Subfinder",
                "url": "https://github.com/projectdiscovery/subfinder",
                "icon": "🌐",
                "description": "Enumeração passiva de subdomínios",
                "use_for": "Subdomínios de um domínio-alvo autorizado",
                "source": "hackingtool",
            },
            {
                "id": "httpx",
                "name": "httpx",
                "url": "https://github.com/projectdiscovery/httpx",
                "icon": "📡",
                "description": "Probe HTTP rápido (status, título, techs)",
                "use_for": "Lista de hosts/URLs vivos",
                "source": "hackingtool",
            },
            {
                "id": "dnsx",
                "name": "dnsx",
                "url": "https://github.com/projectdiscovery/dnsx",
                "icon": "🧭",
                "description": "Toolkit DNS multipropósito",
                "use_for": "Resolução e enum DNS",
                "source": "hackingtool",
            },
            {
                "id": "theharvester",
                "name": "theHarvester",
                "url": "https://github.com/laramies/theHarvester",
                "icon": "🌾",
                "description": "Emails, hosts e subdomínios em fontes abertas",
                "use_for": "Email e domínio (já no OSINT Avançado se instalado)",
                "source": "hackingtool",
            },
            {
                "id": "amass",
                "name": "OWASP Amass",
                "url": "https://github.com/owasp-amass/amass",
                "icon": "🗺️",
                "description": "Mapeamento de superfície de ataque",
                "use_for": "Subdomínios e assets de domínio",
                "source": "hackingtool",
            },
            {
                "id": "gitleaks",
                "name": "Gitleaks",
                "url": "https://github.com/gitleaks/gitleaks",
                "icon": "🔐",
                "description": "Scanner de segredos em repositórios Git",
                "use_for": "Repo autorizado / vazamento de secrets",
                "source": "hackingtool",
            },
            {
                "id": "trufflehog",
                "name": "TruffleHog",
                "url": "https://github.com/trufflesecurity/trufflehog",
                "icon": "🐷",
                "description": "Caça secrets em git e arquivos",
                "use_for": "API keys e credenciais em código",
                "source": "hackingtool",
            },
        ],
    },
}


def get_categories():
    """Lista ordenada de chaves de categoria."""
    return list(EXTERNAL_SERVICES.keys())


def get_category(category_key):
    """Retorna uma categoria pelo id interno."""
    return EXTERNAL_SERVICES.get(category_key)


def get_all_categories():
    """Todas as categorias com dados completos."""
    return EXTERNAL_SERVICES


def get_services_for_page(page_key):
    """Serviços cujo page_keys inclui a página atual."""
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
