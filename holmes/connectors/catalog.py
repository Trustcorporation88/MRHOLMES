"""
Catálogo de deeplinks.

Aqui mora a maior mudança prática do projeto: antes, os 89 serviços abriam
a HOME e você redigitava o alvo. Agora cada um recebe um template e abre
JÁ PESQUISADO. Onde o serviço exige login ou captcha, isso é declarado como
MANUAL — o console não finge que funciona.

Template usa as variáveis do `Entity.variants`:
  {value} {digits} {e164} {local} {domain} {root} {handle} {quoted} {plus} ...
"""

from __future__ import annotations

from urllib.parse import quote, quote_plus

from ..entity import Entity, EntityType
from .base import Connector, Mode, register

E = EntityType.EMAIL
U = EntityType.USERNAME
P = EntityType.PHONE
N = EntityType.NAME
D = EntityType.DOMAIN
I = EntityType.IP
CPF = EntityType.CPF
CNPJ = EntityType.CNPJ
PROF = EntityType.PROFILE_URL
PROC = EntityType.PROCESSO
PLACA = EntityType.PLACA


def _fmt(template: str, entity: Entity) -> str | None:
    """Preenche o template. Se faltar variável essencial, o link não é gerado."""
    data = {
        "value": entity.value,
        "raw": entity.raw,
        "ascii": entity.get("ascii") or entity.value,
        "digits": entity.get("digits") or "",
        "e164": entity.get("e164") or entity.value,
        "local": entity.get("local") or "",
        "national": entity.get("national") or "",
        "domain": entity.get("domain") or entity.value,
        "root": entity.get("root") or entity.value,
        "handle": entity.get("handle") or entity.get("username_guess") or entity.value,
        "first": entity.get("first") or "",
        "last": entity.get("last") or "",
        "ip": entity.value,
    }
    out = template
    for key, val in data.items():
        token = "{" + key + "}"
        if token in out:
            if not val:
                return None
            out = out.replace(token, quote(str(val), safe=""))
        token_p = "{" + key + "+}"
        if token_p in out:
            if not val:
                return None
            out = out.replace(token_p, quote_plus(str(val)))
    return out


def _make_deeplink(template: str):
    def _fn(entity: Entity) -> str | None:
        return _fmt(template, entity)
    return _fn


def _homepage(url: str):
    def _fn(_entity: Entity) -> str:
        return url
    return _fn


# (id, rótulo, categoria, tipos aceitos, modo, template ou url, descrição)
_CATALOG: list[tuple] = [
    # ── Motores de busca com o alvo entre aspas ─────────────────────────────
    ("g_exato", "Google — termo exato", "busca", (N, E, P, U, CPF, CNPJ, PLACA), Mode.DEEPLINK,
     'https://www.google.com/search?q=%22{value+}%22', "Busca literal, sem sinônimos"),
    ("g_social", "Google — só redes sociais", "busca", (N, U), Mode.DEEPLINK,
     'https://www.google.com/search?q=%22{value+}%22+(site%3Ainstagram.com+OR+site%3Alinkedin.com+OR+site%3Afacebook.com+OR+site%3Ax.com)',
     "Restringe às principais redes de uma vez"),
    ("g_docs", "Google — documentos", "busca", (N, E, CNPJ), Mode.DEEPLINK,
     'https://www.google.com/search?q=%22{value+}%22+(filetype%3Apdf+OR+filetype%3Adocx+OR+filetype%3Axlsx)',
     "PDF, DOCX e planilhas que citam o alvo"),
    ("yandex", "Yandex", "busca", (N, E, P, U), Mode.DEEPLINK,
     'https://yandex.com/search/?text=%22{value+}%22',
     "Indexa conteúdo que o Google removeu ou nunca pegou"),
    ("bing", "Bing", "busca", (N, E, P, U), Mode.DEEPLINK,
     'https://www.bing.com/search?q=%22{value+}%22', "Índice alternativo"),
    ("ddg", "DuckDuckGo", "busca", (N, E, P, U), Mode.DEEPLINK,
     'https://duckduckgo.com/?q=%22{value+}%22', "Sem personalização de resultado"),

    # ── Redes sociais: busca interna já preenchida ──────────────────────────
    ("linkedin", "LinkedIn — pessoas", "social", (N,), Mode.DEEPLINK,
     'https://www.linkedin.com/search/results/people/?keywords={value+}',
     "Busca de pessoas (exige estar logado)"),
    ("linkedin_co", "LinkedIn — empresas", "social", (D, CNPJ), Mode.DEEPLINK,
     'https://www.linkedin.com/search/results/companies/?keywords={value+}', "Página da organização"),
    ("facebook", "Facebook — busca", "social", (N, U, P), Mode.DEEPLINK,
     'https://www.facebook.com/search/top?q={value+}', "Perfis, páginas e publicações"),
    ("instagram", "Instagram — perfil direto", "social", (U,), Mode.DEEPLINK,
     'https://www.instagram.com/{handle}/', "Abre o perfil do handle"),
    ("instagram_b", "Instagram — busca", "social", (N,), Mode.DEEPLINK,
     'https://www.instagram.com/explore/search/keyword/?q={value+}', "Busca por nome"),
    ("x_search", "X/Twitter — busca", "social", (N, U, E, P), Mode.DEEPLINK,
     'https://x.com/search?q=%22{value+}%22&f=user', "Contas que batem com o termo"),
    ("tiktok", "TikTok — busca", "social", (N, U), Mode.DEEPLINK,
     'https://www.tiktok.com/search/user?q={value+}', "Contas no TikTok"),
    ("github_s", "GitHub — busca de usuários", "social", (N, U, E), Mode.DEEPLINK,
     'https://github.com/search?q={value+}&type=users', "Contas de desenvolvedor"),
    ("github_code", "GitHub — código citando o alvo", "social", (E, D, P), Mode.DEEPLINK,
     'https://github.com/search?q=%22{value+}%22&type=code',
     "E-mail/telefone esquecido em commit ou config"),
    ("telegram", "Telegram — handle", "social", (U,), Mode.DEEPLINK,
     'https://t.me/{handle}', "Abre o perfil/canal se existir"),
    ("youtube", "YouTube — busca", "social", (N, U), Mode.DEEPLINK,
     'https://www.youtube.com/results?search_query={value+}', "Canais e vídeos"),
    ("reddit", "Reddit — usuário", "social", (U,), Mode.DEEPLINK,
     'https://www.reddit.com/user/{handle}', "Perfil e histórico público"),

    # ── Telefone (catálogo do usuário, agora com o número embutido) ─────────
    ("syncme", "Sync.me", "telefone", (P,), Mode.DEEPLINK,
     'https://sync.me/search/?number={e164}', "Caller ID colaborativo"),
    ("truecaller", "Truecaller", "telefone", (P,), Mode.DEEPLINK,
     'https://www.truecaller.com/search/br/{digits}', "Nome associado ao número (exige login)"),
    ("freelookup", "Free-Lookup", "telefone", (P,), Mode.DEEPLINK,
     'https://free-lookup.net/{digits}', "Operadora e tipo de linha"),
    ("spamcalls", "SpamCalls", "telefone", (P,), Mode.DEEPLINK,
     'https://spamcalls.net/en/num/{digits}', "Reputação e denúncias de spam"),
    ("numlookup", "NumLookup", "telefone", (P,), Mode.DEEPLINK,
     'https://www.numlookup.com/?phone={digits}', "Consulta reversa gratuita"),
    ("whatsapp_dl", "WhatsApp", "telefone", (P,), Mode.DEEPLINK,
     'https://wa.me/{digits}', "Foto e nome de exibição, se a conta existir"),
    ("quemperturba", "Quem Perturba", "telefone", (P,), Mode.DEEPLINK,
     'https://www.quemperturba.com.br/numero/{digits}', "Base brasileira de denúncia de spam"),
    ("getcontact", "GetContact", "telefone", (P,), Mode.MANUAL,
     "https://www.getcontact.com/", "Como o número está salvo na agenda de terceiros (só no app)"),
    ("callapp", "CallApp", "telefone", (P,), Mode.MANUAL,
     "https://callapp.com/", "Caller ID por aplicativo"),
    ("eyecon", "Eyecon", "telefone", (P,), Mode.MANUAL,
     "https://www.eyecon-app.com/", "Foto do contato via agenda colaborativa"),
    ("spydialer", "SpyDialer", "telefone", (P,), Mode.MANUAL,
     "https://www.spydialer.com/", "Consulta reversa (formulário com captcha)"),
    ("whosenumber", "WhoseNumber", "telefone", (P,), Mode.MANUAL,
     "https://whosenumber.info/", "Consulta reversa"),
    ("phonebook_cz", "Phonebook.cz", "telefone", (P, D, E), Mode.MANUAL,
     "https://phonebook.cz/", "Base da Intelligence X (exige conta)"),

    # ── E-mail ──────────────────────────────────────────────────────────────
    ("emailrep", "EmailRep", "email", (E,), Mode.DEEPLINK,
     'https://emailrep.io/{value}', "Reputação, idade e perfis vinculados"),
    ("hunter_dl", "Hunter.io", "email", (D,), Mode.DEEPLINK,
     'https://hunter.io/search/{root}', "E-mails públicos do domínio"),
    ("mxtoolbox", "MxToolbox", "email", (D, E), Mode.DEEPLINK,
     'https://mxtoolbox.com/SuperTool.aspx?action=mx%3a{domain}&run=toolpage',
     "MX, SPF, DMARC e blacklist"),
    ("epieos", "Epieos", "email", (E, P), Mode.MANUAL,
     "https://epieos.com/", "Contas Google/serviços por e-mail (exige conta)"),

    # ── Vazamentos ──────────────────────────────────────────────────────────
    ("intelx", "Intelligence X", "leaks", (E, D, P, N, CPF, CNPJ), Mode.DEEPLINK,
     'https://intelx.io/?s={value+}', "Documentos, pastes e leaks históricos"),
    ("dehashed", "Dehashed", "leaks", (E, U, P, N, D), Mode.DEEPLINK,
     'https://www.dehashed.com/search?query={value+}', "Base de credenciais vazadas (assinatura)"),
    ("psbdmp", "PSBDMP", "leaks", (E, U, D), Mode.DEEPLINK,
     'https://psbdmp.ws/search/{value}', "Pastes públicos que citam o alvo"),
    ("hibp_dl", "Have I Been Pwned", "leaks", (E,), Mode.MANUAL,
     "https://haveibeenpwned.com/", "Vazamentos por e-mail (formulário)"),
    ("hudsonrock", "Hudson Rock", "leaks", (E, D, U), Mode.MANUAL,
     "https://www.hudsonrock.com/free-tools", "Infostealer: máquina infectada com a credencial"),
    ("leakcheck", "LeakCheck", "leaks", (E, U, P), Mode.MANUAL,
     "https://leakcheck.io/", "Busca em leaks (exige conta)"),
    ("osintleak", "OSINT Leak", "leaks", (E, U, P, N), Mode.MANUAL,
     "https://app.osintleak.com/dashboard/search", "Dashboard próprio (API paga)"),
    ("crackstation", "CrackStation", "leaks", (), Mode.MANUAL,
     "https://crackstation.net/", "Reverte hash conhecido (só com o hash em mãos)"),

    # ── Domínio / infraestrutura ────────────────────────────────────────────
    ("webcheck", "Web-Check", "dominio", (D,), Mode.DEEPLINK,
     'https://web-check.xyz/check/https%3A%2F%2F{root}', "Raio-x completo do site"),
    ("crtsh_dl", "crt.sh", "dominio", (D,), Mode.DEEPLINK,
     'https://crt.sh/?q=%25.{root}', "Certificados e subdomínios"),
    ("securitytrails", "SecurityTrails", "dominio", (D,), Mode.DEEPLINK,
     'https://securitytrails.com/domain/{root}/dns', "Histórico de DNS e WHOIS"),
    ("urlscan", "urlscan.io", "dominio", (D,), Mode.DEEPLINK,
     'https://urlscan.io/search/#{root}', "Capturas e comportamento do site"),
    ("viewdns", "ViewDNS — IP reverso", "dominio", (D, I), Mode.DEEPLINK,
     'https://viewdns.info/reverseip/?host={value}&t=1', "Outros domínios no mesmo servidor"),
    ("virustotal", "VirusTotal", "dominio", (D,), Mode.DEEPLINK,
     'https://www.virustotal.com/gui/domain/{root}', "Reputação e relações do domínio"),
    ("virustotal_ip", "VirusTotal (IP)", "rede", (I,), Mode.DEEPLINK,
     'https://www.virustotal.com/gui/ip-address/{ip}', "Reputação do IP"),
    ("ssllabs", "SSL Labs", "dominio", (D,), Mode.DEEPLINK,
     'https://www.ssllabs.com/ssltest/analyze.html?d={root}', "Qualidade do TLS"),
    ("securityheaders", "SecurityHeaders", "dominio", (D,), Mode.DEEPLINK,
     'https://securityheaders.com/?q={root}&followRedirects=on', "Cabeçalhos de segurança"),
    ("builtwith", "BuiltWith", "dominio", (D,), Mode.DEEPLINK,
     'https://builtwith.com/{root}', "Tecnologias, analytics e rastreadores"),
    ("shodan_dl", "Shodan", "dominio", (D, I), Mode.DEEPLINK,
     'https://www.shodan.io/search?query={value+}', "Portas e serviços expostos"),
    ("censys", "Censys", "dominio", (D, I), Mode.DEEPLINK,
     'https://search.censys.io/search?resource=hosts&q={value+}', "Hosts e certificados"),
    ("ipinfo_dl", "IPinfo", "rede", (I,), Mode.DEEPLINK,
     'https://ipinfo.io/{ip}', "ASN, organização e geolocalização"),
    ("dnsdumpster", "DNSDumpster", "dominio", (D,), Mode.MANUAL,
     "https://dnsdumpster.com/", "Mapa de DNS (formulário com token)"),

    # ── Arquivo e histórico ─────────────────────────────────────────────────
    ("wayback", "Wayback Machine", "arquivo", (D,), Mode.DEEPLINK,
     'https://web.archive.org/web/*/{root}/*', "Versões antigas do site"),
    ("wayback_t", "Wayback — menções", "arquivo", (N, E, U), Mode.DEEPLINK,
     'https://web.archive.org/web/*/{value+}', "Conteúdo apagado que ainda existe no arquivo"),
    ("archive_today", "archive.today", "arquivo", (D, N, U), Mode.DEEPLINK,
     'https://archive.ph/search/?q={value+}', "Capturas independentes do Wayback"),

    # ── Imagem ──────────────────────────────────────────────────────────────
    ("google_img", "Google Imagens", "imagem", (N,), Mode.DEEPLINK,
     'https://www.google.com/search?tbm=isch&q=%22{value+}%22', "Fotos associadas ao nome"),
    ("yandex_img", "Yandex Imagens", "imagem", (N,), Mode.DEEPLINK,
     'https://yandex.com/images/search?text=%22{value+}%22', "Melhor motor para rosto"),
    ("tineye", "TinEye", "imagem", (), Mode.MANUAL,
     "https://tineye.com/", "Busca reversa por upload"),
    ("google_lens", "Google Lens", "imagem", (), Mode.MANUAL,
     "https://lens.google.com/", "Busca reversa por imagem"),
    ("jimpl", "Jimpl", "imagem", (), Mode.MANUAL,
     "https://jimpl.com/", "EXIF e coordenadas da foto"),
    ("fotoforensics", "FotoForensics", "imagem", (), Mode.MANUAL,
     "https://fotoforensics.com/", "Detecta edição na imagem"),
    ("aperisolve", "Aperi'Solve", "imagem", (), Mode.MANUAL,
     "https://www.aperisolve.com/", "Esteganografia"),
    ("stegonline", "StegOnline", "imagem", (), Mode.MANUAL,
     "https://georgeom.net/StegOnline/upload", "Análise de camadas de bit"),
    ("invid", "InVID", "imagem", (), Mode.MANUAL,
     "https://www.invid-project.eu/tools-and-services/invid-verification-plugin/",
     "Verificação de vídeo"),

    # ── Corporativo e investigativo ─────────────────────────────────────────
    ("opencorporates", "OpenCorporates", "corporativo", (N, CNPJ, D), Mode.DEEPLINK,
     'https://opencorporates.com/companies?q={value+}', "Empresas e diretores no mundo todo"),
    ("aleph", "OCCRP Aleph", "corporativo", (N, E, CNPJ, CPF), Mode.DEEPLINK,
     'https://aleph.occrp.org/search?q={value+}', "Vazamentos jornalísticos e registros públicos"),

    # ── Dark web ────────────────────────────────────────────────────────────
    ("ahmia", "Ahmia", "darkweb", (N, E, U, D), Mode.DEEPLINK,
     'https://ahmia.fi/search/?q={value+}', "Índice .onion pela clearnet"),

    # ── Ferramentas que exigem instalação (referência, não fonte) ───────────
    ("cyberchef", "CyberChef", "utilitario", (), Mode.MANUAL,
     "https://gchq.github.io/CyberChef/", "Decodificação e transformação de dados"),
    ("wigle", "WiGLE", "utilitario", (), Mode.MANUAL,
     "https://wigle.net/", "Geolocalização por rede Wi-Fi"),
    ("bellingcat_osm", "Bellingcat OSM Search", "utilitario", (), Mode.MANUAL,
     "https://osm-search.bellingcat.com/", "Encontra lugar pela descrição do entorno"),
    ("namechk", "Namechk", "username", (U,), Mode.MANUAL,
     "https://namechk.com/", "Disponibilidade de handle (página em JS)"),
    ("mind", "Mind Search", "pessoas", (N, CPF, P), Mode.MANUAL,
     "https://mind-7.org/?r=fala_melo", "Busca de pessoas (seu link)"),
    ("osintframework", "OSINT Framework", "pessoas", (), Mode.MANUAL,
     "https://osintframework.com/", "Mapa de fontes por tipo de alvo"),
]

# Repositórios: referência de arsenal, não fonte consultável.
ARSENAL_REPOS = [
    ("sherlock", "Sherlock", "https://github.com/sherlock-project/sherlock", "username"),
    ("maigret_repo", "Maigret", "https://github.com/soxoj/maigret", "username"),
    ("socialscan", "SocialScan", "https://github.com/iojw/socialscan", "username"),
    ("whatsmyname_repo", "WhatsMyName", "https://github.com/WebBreacher/WhatsMyName", "username"),
    ("blackbird", "Blackbird", "https://github.com/p1ngul1n0/blackbird", "username"),
    ("social-analyzer", "Social Analyzer", "https://github.com/qeeqbox/social-analyzer", "username"),
    ("nexfil", "NExfil", "https://github.com/thewhiteh4t/nexfil", "username"),
    ("phoneinfoga", "PhoneInfoga", "https://github.com/sundowndev/phoneinfoga", "telefone"),
    ("ignorant", "Ignorant", "https://github.com/megadose/ignorant", "telefone"),
    ("phunter", "Phunter", "https://github.com/N0rz3/Phunter", "telefone"),
    ("searchphone", "SearchPhone", "https://github.com/HackUnderway/SearchPhone", "telefone"),
    ("moriarty", "Moriarty Project", "https://github.com/AzizKpln/Moriarty-Project", "telefone"),
    ("telephone-osint", "Telephone-OSINT Toolbox", "https://github.com/The-Osint-Toolbox/Telephone-OSINT", "telefone"),
    ("holehe_repo", "Holehe", "https://github.com/megadose/holehe", "email"),
    ("h8mail", "h8mail", "https://github.com/khast3x/h8mail", "email"),
    ("ghunt", "GHunt", "https://github.com/mxrch/GHunt", "email"),
    ("gitfive", "GitFive", "https://github.com/mxrch/GitFive", "username"),
    ("subfinder", "Subfinder", "https://github.com/projectdiscovery/subfinder", "dominio"),
    ("httpx", "httpx", "https://github.com/projectdiscovery/httpx", "dominio"),
    ("dnsx", "dnsx", "https://github.com/projectdiscovery/dnsx", "dominio"),
    ("theharvester", "theHarvester", "https://github.com/laramies/theHarvester", "dominio"),
    ("amass", "OWASP Amass", "https://github.com/owasp-amass/amass", "dominio"),
    ("gitleaks", "Gitleaks", "https://github.com/gitleaks/gitleaks", "dominio"),
    ("trufflehog", "TruffleHog", "https://github.com/trufflesecurity/trufflehog", "dominio"),
    ("photon", "Photon", "https://github.com/s0md3v/Photon", "dominio"),
    ("robin", "Robin", "https://github.com/apurvsinghgautam/robin", "darkweb"),
    ("robin-tools-list", "Dark Web OSINT Tools", "https://github.com/apurvsinghgautam/dark-web-osint-tools", "darkweb"),
    ("flowsint", "Flowsint", "https://github.com/reconurge/flowsint", "grafo"),
    ("arsenal-index", "Awesome OSINT Arsenal", "https://github.com/rawfilejson/awesome-osint-arsenal", "indice"),
    ("hackingtool", "hackingtool", "https://github.com/Z4nzu/hackingtool", "indice"),
]


def register_catalog() -> None:
    for cid, label, category, accepts, mode, target, desc in _CATALOG:
        if not accepts:
            # Ferramenta sem alvo aplicável (upload de imagem, hash…): fica no arsenal.
            continue
        if mode is Mode.DEEPLINK:
            fn = _make_deeplink(target)
            homepage = target.split("?")[0]
        else:
            fn = _homepage(target)
            homepage = target
        register(Connector(
            id=cid, label=label, mode=mode, accepts=tuple(accepts),
            category=category, description=desc, homepage=homepage, deeplink=fn,
        ))


def register_br_catalog() -> None:
    """Deeplinks brasileiros — gerados a partir de holmes.br."""
    from .. import br

    PLACA = EntityType.PLACA
    specs = {
        N: br.br_deeplinks,
        PROC: br.br_deeplinks,
        CNPJ: br.br_deeplinks,
        CPF: br.br_deeplinks,
        P: br.br_deeplinks,
        PLACA: br.br_deeplinks,
    }

    def _make(idx: int, entity_types: tuple):
        def _fn(entity: Entity) -> str | None:
            links = br.br_deeplinks(entity)
            return links[idx][1] if idx < len(links) else None
        return _fn

    # Um conector por posição de cada tipo, para aparecerem separados no dossiê.
    seen: set[str] = set()
    from ..entity import Entity as _E

    samples = {
        N: _E(raw="a b", type=N, value="a b", variants={"ascii": "a b"}),
        PROC: _E(raw="0000133-39.2025.8.26.0334", type=PROC,
                 value="0000133-39.2025.8.26.0334",
                 variants={"digits": "00001333920258260334",
                           "cnj": {"sigla": "TJSP", "digits": "00001333920258260334"}}),
        CNPJ: _E(raw="00000000000191", type=CNPJ, value="00.000.000/0001-91",
                 variants={"digits": "00000000000191"}),
        CPF: _E(raw="00000000191", type=CPF, value="000.000.001-91",
                variants={"digits": "00000000191"}),
        P: _E(raw="+5511999999999", type=P, value="+5511999999999",
              variants={"country": "BR", "digits": "5511999999999",
                        "e164": "+5511999999999"}),
        PLACA: _E(raw="ABC1D23", type=PLACA, value="ABC1D23",
                  variants={"placa": "ABC1D23"}),
    }
    for etype, sample in samples.items():
        for idx, (rotulo, _url, desc) in enumerate(br.br_deeplinks(sample)):
            cid = f"br_{etype.value}_{idx}"
            if cid in seen:
                continue
            seen.add(cid)
            register(Connector(
                id=cid, label=f"{rotulo} (BR)", mode=Mode.DEEPLINK,
                accepts=(etype,), category="brasil", description=desc,
                deeplink=_make(idx, (etype,)),
            ))
