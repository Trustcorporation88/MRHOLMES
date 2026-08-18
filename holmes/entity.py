"""
Detecção e normalização do alvo.

O usuário digita uma coisa só numa caixa só. Aqui a gente descobre o que é
e produz todas as formas úteis daquele dado (E.164, local-part, domínio raiz,
CPF sem pontuação…), que é o que os conectores consomem.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class EntityType(str, Enum):
    NAME = "nome"
    EMAIL = "email"
    PHONE = "telefone"
    USERNAME = "username"
    DOMAIN = "dominio"
    IP = "ip"
    CPF = "cpf"
    CNPJ = "cnpj"
    PROFILE_URL = "perfil"
    UNKNOWN = "desconhecido"


ENTITY_LABEL = {
    EntityType.NAME: "Nome",
    EntityType.EMAIL: "E-mail",
    EntityType.PHONE: "Telefone",
    EntityType.USERNAME: "Username",
    EntityType.DOMAIN: "Domínio",
    EntityType.IP: "IP",
    EntityType.CPF: "CPF",
    EntityType.CNPJ: "CNPJ",
    EntityType.PROFILE_URL: "URL de perfil",
    EntityType.UNKNOWN: "Indefinido",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
_IPV4_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$", re.I
)
_HANDLE_RE = re.compile(r"^@?[a-z0-9](?:[a-z0-9._-]{1,38})$", re.I)

# gTLDs comuns. Qualquer rótulo final de 2 letras é tratado como ccTLD.
# Sem isso, "joao.silva" (local-part de e-mail) seria confundido com domínio.
_GTLDS = {
    "com", "net", "org", "edu", "gov", "mil", "int", "info", "biz", "name",
    "pro", "app", "dev", "io", "ai", "co", "me", "tv", "cc", "xyz", "site",
    "online", "store", "shop", "tech", "cloud", "space", "website", "blog",
    "news", "media", "agency", "digital", "studio", "design", "email", "live",
    "life", "world", "today", "group", "solutions", "services", "systems",
    "network", "center", "company", "global", "team", "works", "zone", "link",
    "click", "page", "wiki", "art", "fun", "top", "vip", "one", "run", "sh",
    "gg", "so", "to", "ly", "am", "fm", "gl", "im", "is", "it", "la", "ms",
}


def _looks_like_domain(text: str) -> bool:
    if not _DOMAIN_RE.match(text):
        return False
    tld = text.rsplit(".", 1)[-1].lower()
    return (len(tld) == 2 and tld.isalpha()) or tld in _GTLDS

# Plataformas cujo path já entrega o handle.
_PROFILE_HOSTS = {
    "instagram.com": 1,
    "www.instagram.com": 1,
    "twitter.com": 1,
    "x.com": 1,
    "www.x.com": 1,
    "github.com": 1,
    "www.github.com": 1,
    "tiktok.com": 1,
    "www.tiktok.com": 1,
    "facebook.com": 1,
    "www.facebook.com": 1,
    "t.me": 1,
    "telegram.me": 1,
    "reddit.com": 2,
    "www.reddit.com": 2,
    "linkedin.com": 2,
    "www.linkedin.com": 2,
    "br.linkedin.com": 2,
    "youtube.com": 1,
    "www.youtube.com": 1,
    "medium.com": 1,
    "twitch.tv": 1,
    "www.twitch.tv": 1,
    "kwai.com": 1,
    "threads.net": 1,
    "www.threads.net": 1,
}

# DDDs válidos no Brasil (o resto é digitação errada).
_DDD_BR = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99,
}

_PARTICLES = {"de", "da", "do", "das", "dos", "e", "di", "del", "van", "von", "la", "le"}


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def only_digits(text: str) -> str:
    return "".join(c for c in (text or "") if c.isdigit())


def valid_cpf(raw: str) -> bool:
    """Validação real de dígito verificador — evita disparar busca com número inventado."""
    d = only_digits(raw)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(d[i]) * ((size + 1) - i) for i in range(size))
        check = (total * 10) % 11
        check = 0 if check == 10 else check
        if check != int(d[size]):
            return False
    return True


def valid_cnpj(raw: str) -> bool:
    d = only_digits(raw)
    if len(d) != 14 or d == d[0] * 14:
        return False
    for size, weights in (
        (12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
        (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
    ):
        total = sum(int(d[i]) * weights[i] for i in range(size))
        rest = total % 11
        check = 0 if rest < 2 else 11 - rest
        if check != int(d[size]):
            return False
    return True


def format_cpf(raw: str) -> str:
    d = only_digits(raw)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else raw


def format_cnpj(raw: str) -> str:
    d = only_digits(raw)
    if len(d) != 14:
        return raw
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


@dataclass
class Entity:
    """O alvo normalizado. `variants` é o que alimenta dork e deeplink."""

    raw: str
    type: EntityType
    value: str
    variants: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return ENTITY_LABEL.get(self.type, self.type.value)

    def get(self, key: str, default: Any = None) -> Any:
        return self.variants.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "type": self.type.value,
            "label": self.label,
            "value": self.value,
            "variants": self.variants,
            "notes": self.notes,
        }


# ── normalizadores por tipo ──────────────────────────────────────────────────

def _norm_email(raw: str) -> Entity:
    value = raw.strip().lower()
    local, _, domain = value.partition("@")
    # Gmail ignora ponto e sufixo +tag — o mesmo dono, escritas diferentes.
    canonical = local.split("+")[0]
    if domain in {"gmail.com", "googlemail.com"}:
        canonical = canonical.replace(".", "")
    handle = re.sub(r"[^a-z0-9._-]", "", canonical)
    variants = {
        "local": local,
        "domain": domain,
        "canonical": f"{canonical}@{domain}",
        "username_guess": handle,
        "quoted": f'"{value}"',
    }
    return Entity(raw=raw, type=EntityType.EMAIL, value=value, variants=variants)


def _norm_phone(raw: str) -> Entity:
    digits = only_digits(raw)
    explicit_cc = raw.strip().startswith("+")

    # Brasil por padrão: 10/11 dígitos com DDD válido vira +55.
    if not explicit_cc and len(digits) in (10, 11) and int(digits[:2] or 0) in _DDD_BR:
        digits = "55" + digits

    e164 = "+" + digits
    variants: dict[str, Any] = {"digits": digits, "e164": e164}

    if digits.startswith("55") and len(digits) in (12, 13):
        ddd = digits[2:4]
        local = digits[4:]
        variants.update(
            {
                "country": "BR",
                "cc": "55",
                "ddd": ddd,
                "local": local,
                "national": f"({ddd}) {local[:-4]}-{local[-4:]}",
                "pretty": f"+55 {ddd} {local[:-4]}-{local[-4:]}",
                "whatsapp": f"https://wa.me/{digits}",
                # Celular BR ganhou o nono dígito; bases antigas guardam sem ele.
                "alt_no9": ("55" + ddd + local[1:]) if len(local) == 9 and local.startswith("9") else None,
            }
        )
    else:
        variants.update({"country": None, "pretty": e164, "whatsapp": f"https://wa.me/{digits}"})

    # Formas de escrita que o Google indexa separadamente.
    forms = [e164, digits, variants.get("national"), variants.get("pretty")]
    variants["search_forms"] = [f for f in forms if f]
    return Entity(raw=raw, type=EntityType.PHONE, value=e164, variants=variants)


def _norm_username(raw: str) -> Entity:
    value = raw.strip().lstrip("@").lower()
    variants = {
        "handle": value,
        "at": f"@{value}",
        "quoted": f'"{value}"',
        "email_guesses": [f"{value}@{d}" for d in ("gmail.com", "hotmail.com", "outlook.com", "yahoo.com.br")],
    }
    return Entity(raw=raw, type=EntityType.USERNAME, value=value, variants=variants)


def _norm_domain(raw: str) -> Entity:
    value = raw.strip().lower().rstrip("/")
    if "://" in value:
        value = urlparse(value).netloc or value
    value = value.split("/")[0]
    if value.startswith("www."):
        value = value[4:]
    parts = value.split(".")
    # Cobre .com.br, .gov.br etc., onde a raiz tem três rótulos.
    if len(parts) > 2 and parts[-2] in {"com", "net", "org", "gov", "edu", "co"} and len(parts[-1]) == 2:
        root = ".".join(parts[-3:])
    else:
        root = ".".join(parts[-2:])
    variants = {
        "root": root,
        "www": f"www.{value}",
        "url": f"https://{value}",
        "site_dork": f"site:{root}",
    }
    return Entity(raw=raw, type=EntityType.DOMAIN, value=value, variants=variants)


def _norm_name(raw: str) -> Entity:
    cleaned = re.sub(r"\s+", " ", raw.strip())
    ascii_name = strip_accents(cleaned).lower()
    tokens = [t for t in ascii_name.split(" ") if t]
    meaningful = [t for t in tokens if t not in _PARTICLES]
    first = meaningful[0] if meaningful else ""
    last = meaningful[-1] if len(meaningful) > 1 else ""

    # Handles que uma pessoa realmente usaria — alimenta a busca por username.
    guesses: list[str] = []
    if first and last:
        guesses = [
            f"{first}{last}", f"{first}.{last}", f"{first}_{last}",
            f"{first[0]}{last}", f"{first}{last[0]}",
        ]
    elif first:
        guesses = [first]

    variants = {
        "ascii": ascii_name,
        "quoted": f'"{cleaned}"',
        "quoted_ascii": f'"{ascii_name}"',
        "tokens": meaningful,
        "first": first,
        "last": last,
        "username_guesses": list(dict.fromkeys(guesses))[:5],
        "plus": cleaned.replace(" ", "+"),
    }
    return Entity(raw=raw, type=EntityType.NAME, value=cleaned, variants=variants)


def _norm_profile_url(raw: str) -> Entity:
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or "").lower()
    depth = _PROFILE_HOSTS.get(host, 1)
    segments = [s for s in (parsed.path or "").split("/") if s]
    handle = ""
    if segments:
        handle = segments[min(depth, len(segments)) - 1]
    handle = handle.lstrip("@")
    platform = host.replace("www.", "").split(".")[0]
    variants = {
        "url": raw if "://" in raw else f"https://{raw}",
        "host": host,
        "platform": platform,
        "handle": handle.lower(),
    }
    ent = Entity(raw=raw, type=EntityType.PROFILE_URL, value=variants["url"], variants=variants)
    if handle:
        ent.notes.append(f"Handle extraído do link: @{handle.lower()} ({platform})")
    return ent


# ── detector ────────────────────────────────────────────────────────────────

def detect(raw: str) -> Entity:
    """Recebe a caixa única e devolve o alvo tipado. Nunca levanta exceção."""
    text = (raw or "").strip()
    if not text:
        return Entity(raw=raw, type=EntityType.UNKNOWN, value="")

    # 1. E-mail — inequívoco.
    if _EMAIL_RE.match(text):
        return _norm_email(text)

    # 2. URL — se for host de perfil conhecido, extrai o handle; senão é domínio.
    if "://" in text or text.startswith("www."):
        host = (urlparse(text if "://" in text else f"https://{text}").netloc or "").lower()
        if host in _PROFILE_HOSTS:
            return _norm_profile_url(text)
        return _norm_domain(text)

    digits = only_digits(text)
    non_digit = re.sub(r"[\d\s().+\-/]", "", text)

    # 3. Documentos BR — só se o dígito verificador fechar.
    if not non_digit:
        if len(digits) == 11 and valid_cpf(digits):
            return Entity(
                raw=text, type=EntityType.CPF, value=format_cpf(digits),
                variants={"digits": digits, "formatted": format_cpf(digits),
                          "quoted": f'"{format_cpf(digits)}"'},
            )
        if len(digits) == 14 and valid_cnpj(digits):
            return Entity(
                raw=text, type=EntityType.CNPJ, value=format_cnpj(digits),
                variants={"digits": digits, "formatted": format_cnpj(digits),
                          "quoted": f'"{format_cnpj(digits)}"'},
            )

    # 4. IPv4.
    m = _IPV4_RE.match(text)
    if m and all(0 <= int(g) <= 255 for g in m.groups()):
        return Entity(raw=text, type=EntityType.IP, value=text, variants={"ip": text})

    # 5. Telefone — só dígitos e pontuação de telefone, tamanho plausível.
    if not non_digit and 8 <= len(digits) <= 15:
        return _norm_phone(text)

    # 6. Handle explícito.
    if text.startswith("@") and _HANDLE_RE.match(text):
        return _norm_username(text)

    # 7. Domínio sem esquema — exige TLD plausível, senão "joao.silva" vira domínio.
    if " " not in text and _looks_like_domain(text):
        return _norm_domain(text)

    # 8. Palavra única sem espaço = username; com espaço = nome de pessoa.
    if " " not in text and _HANDLE_RE.match(text):
        return _norm_username(text)

    return _norm_name(text)


def detect_all(raw: str) -> list[Entity]:
    """
    Para colar um bloco de texto (assinatura de e-mail, print de cadastro) e
    extrair todos os alvos de uma vez.
    """
    text = raw or ""
    found: list[Entity] = []
    seen: set[str] = set()

    patterns = [
        r"[^@\s]+@[a-z0-9.-]+\.[a-z]{2,}",
        r"https?://[^\s\"'<>]+",
        r"\+?\d[\d\s().-]{7,17}\d",
    ]
    for pat in patterns:
        for match in re.findall(pat, text, re.I):
            ent = detect(match.strip())
            key = f"{ent.type.value}:{ent.value}"
            if ent.type is not EntityType.UNKNOWN and key not in seen:
                seen.add(key)
                found.append(ent)
    return found
