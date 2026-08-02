"""
Mr.Holmes — catálogo de serviços externos OSINT, separados por categoria.
Inclui links originais + OSINT do GitHub/hackingtool.
Cada serviço fica apenas na categoria correspondente.
"""

EXTERNAL_SERVICES = {
    "pessoas": {
        "label": "Busca de Pessoas",
        "icon": "🧠",
        "description": "Indivíduos, usernames e perfis públicos",
        "page_keys": ["pessoas", "email", "osint"],
        "services": [
            {
                "id": "mind",
                "name": "Mind Search",
                "url": "https://mind-7.org/?r=fala_melo",
                "icon": "🧠",
                "description": "Busca avançada de informações pessoais",
                "use_for": "Nome, documento, perfil",
                "source": "custom",
            },
            {
                "id": "sherlock",
                "name": "Sherlock",
                "url": "https://github.com/sherlock-project/sherlock",
                "icon": "🕵️",
                "description": "Username em centenas de redes sociais",
                "use_for": "Handle / username",
                "source": "github",
            },
            {
                "id": "socialscan",
                "name": "SocialScan",
                "url": "https://github.com/iojw/socialscan",
                "icon": "👥",
                "description": "Checa username ou email em plataformas",
                "use_for": "Username ou email",
                "source": "github",
            },
            {
                "id": "osintframework",
                "name": "OSINT Framework",
                "url": "https://osintframework.com/",
                "icon": "🗺️",
                "description": "Mapa indexado de fontes OSINT",
                "use_for": "Descobrir fontes por tipo de dado",
                "source": "web",
            },
        ],
    },
    "telefone": {
        "label": "Telefone",
        "icon": "📱",
        "description": "Lookup de números, caller-ID e footprints em redes",
        "page_keys": ["telefone"],
        "services": [
            {
                "id": "syncme",
                "name": "Sync.me",
                "url": "https://sync.me/pt-br/",
                "icon": "📱",
                "description": "Agenda reversa e identificação de contato",
                "use_for": "Caller ID / WhatsApp",
                "source": "web",
            },
            {
                "id": "phoneinfoga",
                "name": "PhoneInfoga",
                "url": "https://github.com/sundowndev/phoneinfoga",
                "icon": "📞",
                "description": "Framework OSINT #1 para números (17k+ ★) — scanners e dorks",
                "use_for": "Número internacional / footprint",
                "source": "github",
            },
            {
                "id": "ignorant",
                "name": "Ignorant",
                "url": "https://github.com/megadose/ignorant",
                "icon": "🔕",
                "description": "Verifica se o número está em Instagram, Snapchat etc. (megadose)",
                "use_for": "Número → contas sociais",
                "source": "github",
            },
            {
                "id": "phunter",
                "name": "Phunter",
                "url": "https://github.com/N0rz3/Phunter",
                "icon": "🔎",
                "description": "Coleta informações diversas a partir de um telefone",
                "use_for": "Recon multiponto por número",
                "source": "github",
            },
            {
                "id": "searchphone",
                "name": "SearchPhone",
                "url": "https://github.com/HackUnderway/SearchPhone",
                "icon": "🛰️",
                "description": "Toolkit multi-API (Google, GitHub, Numverify, Reddit…)",
                "use_for": "Busca ampla + relatório",
                "source": "github",
            },
            {
                "id": "moriarty",
                "name": "Moriarty Project",
                "url": "https://github.com/AzizKpln/Moriarty-Project",
                "icon": "🧩",
                "description": "Informações e footprints a partir do número informado",
                "use_for": "Perfil básico do número",
                "source": "github",
            },
            {
                "id": "telephone-osint",
                "name": "Telephone-OSINT Toolbox",
                "url": "https://github.com/The-Osint-Toolbox/Telephone-OSINT",
                "icon": "🧰",
                "description": "Coleção curada de ferramentas de phone lookup",
                "use_for": "Referência de fontes e tools",
                "source": "github",
            },
            {
                "id": "phonebook-cz",
                "name": "Phonebook.cz",
                "url": "https://phonebook.cz/",
                "icon": "📒",
                "description": "Busca em dumps públicos (IntelX related)",
                "use_for": "Número / email em dumps indexados",
                "source": "web",
            },
            {
                "id": "truecaller",
                "name": "Truecaller",
                "url": "https://www.truecaller.com/",
                "icon": "✅",
                "description": "Caller ID colaborativo (requer conta)",
                "use_for": "Nome associado ao número",
                "source": "web",
            },
            {
                "id": "freelookup",
                "name": "Free-Lookup",
                "url": "https://free-lookup.net/",
                "icon": "🌐",
                "description": "Lookup web gratuito de números",
                "use_for": "Consulta rápida online",
                "source": "web",
            },
            {
                "id": "spamcalls",
                "name": "SpamCalls",
                "url": "https://spamcalls.net/",
                "icon": "🚫",
                "description": "Reputação de spam / denúncias de número",
                "use_for": "Número suspeito de spam",
                "source": "web",
            },
            {
                "id": "whosenumber",
                "name": "WhoseNumber",
                "url": "https://whosenumber.info/",
                "icon": "❓",
                "description": "Comentários e reputação de números",
                "use_for": "Quem ligou / reclamações",
                "source": "web",
            },
            {
                "id": "callapp",
                "name": "CallApp",
                "url": "https://callapp.com/",
                "icon": "📲",
                "description": "Caller ID e bloqueio de spam",
                "use_for": "Identificação de contato",
                "source": "web",
            },
            {
                "id": "eyecon",
                "name": "Eyecon",
                "url": "https://www.eyecon-app.com/",
                "icon": "👁️",
                "description": "Caller ID com foto de contato (app)",
                "use_for": "Foto/nome associado",
                "source": "web",
            },
        ],
    },
    "leaks": {
        "label": "Leaks e Vazamentos",
        "icon": "🔓",
        "description": "Breaches, dumps e hashes",
        "page_keys": ["leaks", "email"],
        "services": [
            {
                "id": "dehashed",
                "name": "Dehashed",
                "url": "https://www.dehashed.com/",
                "icon": "🔓",
                "description": "Busca em dumps e violações",
                "use_for": "Email, username, domínio",
                "source": "web",
            },
            {
                "id": "hibp",
                "name": "Have I Been Pwned",
                "url": "https://haveibeenpwned.com/",
                "icon": "📧",
                "description": "Breaches públicos por email",
                "use_for": "Email comprometido",
                "source": "web",
            },
            {
                "id": "crackstation",
                "name": "CrackStation",
                "url": "https://crackstation.net/",
                "icon": "🔑",
                "description": "Lookup de hashes (forense)",
                "use_for": "Hash MD5/SHA",
                "source": "web",
            },
        ],
    },
    "dominio": {
        "label": "Domínio e Website",
        "icon": "🕸️",
        "description": "Sites, DNS e infraestrutura",
        "page_keys": ["dominio", "rede"],
        "services": [
            {
                "id": "webcheck",
                "name": "Web-Check",
                "url": "https://web-check.xyz/",
                "icon": "🕸️",
                "description": "SSL, DNS, headers e fingerprint",
                "use_for": "Domínio / URL",
                "source": "web",
            },
            {
                "id": "crtsh",
                "name": "crt.sh",
                "url": "https://crt.sh/",
                "icon": "📜",
                "description": "Certificate Transparency logs",
                "use_for": "Subdomínios via CT",
                "source": "web",
            },
            {
                "id": "shodan",
                "name": "Shodan",
                "url": "https://www.shodan.io/",
                "icon": "🛰️",
                "description": "Dispositivos e serviços expostos",
                "use_for": "IP / banner / porta",
                "source": "web",
            },
            {
                "id": "urlscan",
                "name": "urlscan.io",
                "url": "https://urlscan.io/",
                "icon": "🧪",
                "description": "Sandbox de URL",
                "use_for": "URL suspeita",
                "source": "web",
            },
            {
                "id": "viewdns",
                "name": "ViewDNS",
                "url": "https://viewdns.info/",
                "icon": "🔎",
                "description": "WHOIS, reverse IP, DNS history",
                "use_for": "Domínio e IP",
                "source": "web",
            },
        ],
    },
    "imagem": {
        "label": "Imagem e Metadados",
        "icon": "🖼️",
        "description": "EXIF, stego e arquivos de imagem",
        "page_keys": ["imagem", "osint"],
        "services": [
            {
                "id": "jimpl",
                "name": "Jimpl",
                "url": "https://jimpl.com/",
                "icon": "🖼️",
                "description": "EXIF/metadados de fotos",
                "use_for": "JPEG/PNG",
                "source": "web",
            },
            {
                "id": "aperisolve",
                "name": "Aperi'Solve",
                "url": "https://www.aperisolve.com/",
                "icon": "🧩",
                "description": "Stego + metadados no browser",
                "use_for": "Imagem com dados ocultos",
                "source": "web",
            },
            {
                "id": "stegonline",
                "name": "StegOnline",
                "url": "https://georgeom.net/StegOnline/upload",
                "icon": "🔬",
                "description": "Explorador LSB",
                "use_for": "Canais de cor / bits",
                "source": "web",
            },
            {
                "id": "exiftool",
                "name": "ExifTool",
                "url": "https://exiftool.org/",
                "icon": "📋",
                "description": "Padrão de metadados imagem/doc",
                "use_for": "EXIF, IPTC, XMP",
                "source": "web",
            },
            {
                "id": "toolsley",
                "name": "Toolsley",
                "url": "https://www.toolsley.com/",
                "icon": "🛠️",
                "description": "Utilitários forenses online",
                "use_for": "Tipo de arquivo / strings",
                "source": "web",
            },
        ],
    },
    "utilitarios": {
        "label": "Utilitários OSINT",
        "icon": "🧰",
        "description": "Decoders e referência",
        "page_keys": ["osint", "utilitarios"],
        "services": [
            {
                "id": "cyberchef",
                "name": "CyberChef",
                "url": "https://gchq.github.io/CyberChef/",
                "icon": "🍳",
                "description": "Encode/decode e transformações",
                "use_for": "Base64, hex, JWT",
                "source": "web",
            },
            {
                "id": "wigle",
                "name": "WiGLE",
                "url": "https://wigle.net/",
                "icon": "📡",
                "description": "Mapa de redes Wi‑Fi",
                "use_for": "SSID / BSSID",
                "source": "web",
            },
            {
                "id": "hackingtool",
                "name": "hackingtool",
                "url": "https://github.com/Z4nzu/hackingtool",
                "icon": "📦",
                "description": "Catálogo 215 tools (referência)",
                "use_for": "Descobrir tools de recon",
                "source": "github",
            },
        ],
    },
    "recon_cli": {
        "label": "Recon CLI",
        "icon": "⚙️",
        "description": "Ferramentas CLI (links oficiais — não instala no site)",
        "page_keys": ["dominio", "osint", "rede"],
        "services": [
            {
                "id": "subfinder",
                "name": "Subfinder",
                "url": "https://github.com/projectdiscovery/subfinder",
                "icon": "🌐",
                "description": "Enum passiva de subdomínios",
                "use_for": "Subdomínios",
                "source": "github",
            },
            {
                "id": "httpx",
                "name": "httpx",
                "url": "https://github.com/projectdiscovery/httpx",
                "icon": "📡",
                "description": "Probe HTTP rápido",
                "use_for": "Hosts vivos",
                "source": "github",
            },
            {
                "id": "dnsx",
                "name": "dnsx",
                "url": "https://github.com/projectdiscovery/dnsx",
                "icon": "🧭",
                "description": "Toolkit DNS",
                "use_for": "Resolução DNS",
                "source": "github",
            },
            {
                "id": "theharvester",
                "name": "theHarvester",
                "url": "https://github.com/laramies/theHarvester",
                "icon": "🌾",
                "description": "Emails e hosts em fontes abertas",
                "use_for": "Email / domínio",
                "source": "github",
            },
            {
                "id": "amass",
                "name": "OWASP Amass",
                "url": "https://github.com/owasp-amass/amass",
                "icon": "🗺️",
                "description": "Superfície de ataque",
                "use_for": "Assets de domínio",
                "source": "github",
            },
            {
                "id": "gitleaks",
                "name": "Gitleaks",
                "url": "https://github.com/gitleaks/gitleaks",
                "icon": "🔐",
                "description": "Secrets em repositórios Git",
                "use_for": "Repo autorizado",
                "source": "github",
            },
            {
                "id": "trufflehog",
                "name": "TruffleHog",
                "url": "https://github.com/trufflesecurity/trufflehog",
                "icon": "🐷",
                "description": "API keys em código",
                "use_for": "Credenciais em git",
                "source": "github",
            },
        ],
    },
}


def get_categories():
    return list(EXTERNAL_SERVICES.keys())


def get_category(category_key):
    return EXTERNAL_SERVICES.get(category_key)


def get_all_categories():
    return EXTERNAL_SERVICES


def get_services_for_page(page_key):
    key = (page_key or "").strip().lower()
    blocks = []
    for cat_key, cat in EXTERNAL_SERVICES.items():
        if key in [k.lower() for k in cat.get("page_keys", [])] or key == cat_key:
            blocks.append((cat_key, cat))
    return blocks


def get_all_services_flat():
    out = []
    for cat_key, cat in EXTERNAL_SERVICES.items():
        for svc in cat.get("services", []):
            item = dict(svc)
            item["category_key"] = cat_key
            item["category_label"] = cat["label"]
            item["category_icon"] = cat["icon"]
            out.append(item)
    return out
