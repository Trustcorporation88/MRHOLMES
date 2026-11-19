"""
Diretório de fontes, no formato de árvore (categoria → fonte).

O dossiê traz só fato. O que exige navegador, login, captcha ou ordem
judicial mora aqui: cada fonte diz o que entrega, quanto custa e abre já
pesquisada no dado digitado sempre que o site aceita o alvo na URL.

Uma fonte só entra se responder ao verificador (`scripts/verificar_diretorio.py`),
que testa cada endereço e confere cada repositório no GitHub.

Marcadores no endereço:
  {q}  o dado como foi digitado      {d}  só os dígitos
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, quote_plus

# custo:   gratis | login (grátis com cadastro) | pago
# acesso:  auto  (já roda sozinho na página Investigar)
#          busca (abre pesquisado no dado)  |  form (você preenche no site)
#          codigo (repositório para rodar localmente)  |  api (contratar e integrar)


@dataclass(frozen=True)
class Fonte:
    nome: str
    url: str
    entrega: str
    custo: str = "gratis"
    acesso: str = "form"
    exemplo: str = ""  # dado válido para o verificador testar a fonte

    def link(self, dado: str = "") -> str:
        """Endereço pronto. Sem dado, cai na página da fonte (marcadores removidos)."""
        dado = (dado or "").strip()
        digitos = "".join(c for c in dado if c.isdigit())
        if "{q}" not in self.url and "{d}" not in self.url:
            return self.url
        if not dado or ("{d}" in self.url and not digitos):
            return self.base
        return self.url.replace("{q}", quote_plus(dado)).replace("{d}", quote(digitos))

    @property
    def base(self) -> str:
        """Raiz do site, para quando não há dado a embutir."""
        partes = self.url.split("/")
        return "/".join(partes[:3]) + "/"

    @property
    def aceita_dado(self) -> bool:
        return "{q}" in self.url or "{d}" in self.url


def _f(nome, url, entrega, custo="gratis", acesso=None, exemplo="") -> Fonte:
    if acesso is None:
        acesso = "busca" if ("{q}" in url or "{d}" in url) else "form"
    return Fonte(nome, url, entrega, custo, acesso, exemplo)


_BDC = "https://bigdatacorp.com.br/"

DIRETORIO: list[tuple[str, str, list[Fonte]]] = [
    ("Pessoa física e CPF", "👤", [
        _f("BigDataCorp: ficha do CPF", _BDC, "Nome, nascimento, mãe, telefones, e-mails, endereços, "
           "empresas, risco financeiro e KYC", "pago", "auto"),
        _f("BigDataCorp: nome → CPF", _BDC, "Candidatos com CPF, nascimento e nome da mãe para separar "
           "homônimos", "pago", "auto"),
        _f("Portal da Transparência: pessoa", "https://portaldatransparencia.gov.br/pessoa-fisica/busca/lista"
           "?termo={q}&pagina=1&tamanhoPagina=10", "Vínculo federal, benefícios, cartão corporativo, sanções"),
        _f("Receita: situação do CPF", "https://servicos.receita.fazenda.gov.br/Servicos/CPF/ConsultaSituacao/"
           "ConsultaPublica.asp", "Situação cadastral e nome. Exige data de nascimento e captcha"),
        _f("Escavador", "https://www.escavador.com/busca?q={q}", "Processos, diários oficiais, currículo e "
           "sociedades por nome", "login"),
        _f("JusBrasil", "https://www.jusbrasil.com.br/busca?q={q}", "Processos e diários por nome. A leitura "
           "automática roda no Investigar", "login"),
        _f("Lattes (CNPq)", "https://buscatextual.cnpq.br/buscatextual/busca.do", "Currículo acadêmico, "
           "vínculos e produção"),
        _f("TSE: candidaturas e bens declarados", "https://divulgacandcontas.tse.jus.br/divulga/",
           "Declaração de bens, doadores e contas de quem já foi candidato"),
        _f("TSE: filiação partidária", "https://www.tse.jus.br/servicos-eleitorais/certidoes/"
           "certidao-de-filiacao-partidaria", "Partido e data de filiação, por certidão"),
        _f("BNMP: mandados de prisão (CNJ)", "https://portalbnmp.cnj.jus.br/#/pesquisa-peca",
           "Mandados de prisão em aberto, por nome ou CPF"),
        _f("Registro Civil: óbitos", "https://www.falecidosnobrasil.org.br/", "Cadastro nacional de falecidos"),
        _f("OAB: cadastro de advogados", "https://cna.oab.org.br/", "Inscrição, seccional e situação"),
        _f("CFM: busca de médicos", "https://portal.cfm.org.br/busca-medicos/", "CRM, especialidade e situação"),
    ]),
    ("Empresa e CNPJ", "🏢", [
        _f("Receita via BrasilAPI", "https://brasilapi.com.br/api/cnpj/v1/{d}", "Cadastro completo e quadro "
           "societário em JSON", "gratis", "auto", "00.000.000/0001-91"),
        _f("BigDataCorp: empresa pelo telefone, e-mail ou nome", _BDC, "Acha o CNPJ a partir de um contato "
           "ou do nome fantasia", "pago", "auto"),
        _f("Minha Receita", "https://minhareceita.org/{d}", "Mesma base da Receita em JSON, sem limite "
           "por minuto. Reserva automática da BrasilAPI", "gratis", "auto", "00.000.000/0001-91"),
        _f("CNPJ.ws (API pública)", "https://publica.cnpj.ws/cnpj/{d}", "Cadastro, sócios e inscrições "
           "estaduais em JSON. Três consultas por minuto", exemplo="00.000.000/0001-91"),
        _f("Receita: comprovante de inscrição", "https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/"
           "cnpjreva_solicitacao.asp", "Cartão CNPJ oficial. Exige captcha"),
        _f("Casa dos Dados", "https://casadosdados.com.br/solucao/cnpj?q={q}", "Busca por razão social, sócio, "
           "CNAE, cidade e data de abertura"),
        _f("CNPJ.biz", "https://cnpj.biz/procura/{q}", "Ficha com sócios e empresas de cada sócio"),
        _f("OpenCorporates", "https://opencorporates.com/companies?q={q}&jurisdiction_code=br",
           "Empresas no Brasil e no exterior, com diretores", "login"),
        _f("Protestos (CENPROT)", "https://www.pesquisaprotesto.com.br/", "Protestos em cartório de todo o país, "
           "por CPF ou CNPJ"),
        _f("PGFN: lista de devedores", "https://www.listadevedores.pgfn.gov.br/", "Dívida ativa da União e FGTS, "
           "por nome ou documento"),
        _f("CNDT: débitos trabalhistas", "https://cndt-certidao.tst.jus.br/inicio.faces", "Certidão de débitos "
           "trabalhistas. Exige captcha"),
        _f("CEIS, CNEP e CEPIM", "https://portaldatransparencia.gov.br/sancoes/consulta?paginacaoSimples=true"
           "&tamanhoPagina=&offset=&direcaoOrdenacao=asc&cpfCnpj={d}", "Empresas e pessoas punidas ou impedidas "
           "de contratar. Também roda no Investigar"),
        _f("INPI: marcas e patentes", "https://busca.inpi.gov.br/pePI/", "Marcas e patentes por titular"),
        _f("Reclame Aqui", "https://www.reclameaqui.com.br/busca/?q={q}", "Reclamações e reputação"),
        _f("Receita: dados abertos do CNPJ", "https://arquivos.receitafederal.gov.br/", "Base completa de empresas e sócios. O índice local de sócios usa estes arquivos"),
    ]),
    ("Processos e Justiça", "⚖️", [
        _f("DataJud (CNJ)", "https://datajud-wiki.cnj.jus.br/api-publica/", "Movimentação oficial pelo número "
           "do processo", "gratis", "auto"),
        _f("BigDataCorp: processos", _BDC, "Lista de processos por CPF ou CNPJ, com tribunal e situação. "
           "Botão dentro do dossiê", "pago", "auto"),
        _f("Jus.br: consulta unificada", "https://www.jus.br/", "Processos de vários tribunais numa busca só",
           "login"),
        _f("TJSP: consulta por nome ou documento", "https://esaj.tjsp.jus.br/cpopg/open.do", "Primeiro grau do "
           "maior tribunal do país, por parte, CPF ou CNPJ"),
        _f("Comunica PJe (DJEN)", "https://comunica.pje.jus.br/consulta?texto={q}", "Intimações e publicações "
           "de todos os tribunais"),
        _f("STJ", "https://processo.stj.jus.br/processo/pesquisa/", "Processos por parte, advogado ou número"),
        _f("STF", "https://portal.stf.jus.br/processos/", "Processos por parte ou número"),
        _f("TST", "https://consultaprocessual.tst.jus.br/consultaProcessual/", "Processos trabalhistas no TST"),
        _f("CNJ: improbidade e inelegibilidade", "https://www.cnj.jus.br/improbidade_adm/"
           "consultar_requerido.php", "Condenações por improbidade, por nome ou documento"),
        _f("TCU: certidões", "https://certidoes-apf.apps.tcu.gov.br/", "Inidôneos, inabilitados e contas "
           "irregulares, numa certidão só"),
        _f("Querido Diário", "https://queridodiario.ok.org.br/pesquisa?term={q}", "Diários oficiais de milhares "
           "de municípios. Também roda no Investigar"),
        _f("Diário Oficial da União", "https://www.in.gov.br/consulta/-/buscar/dou?q={q}", "Nomeações, "
           "contratos, sanções e editais federais"),
    ]),
    ("Patrimônio", "🏠", [
        _f("BigDataCorp: pesquisa completa", _BDC, "Veículos, parentes, participações e débitos. Botão dentro "
           "do dossiê", "pago", "auto"),
        _f("Registradores (ONR)", "https://registradores.onr.org.br/", "Pesquisa de bens imóveis por CPF ou "
           "CNPJ e matrícula online, em cartórios de todo o país", "pago"),
        _f("CENSEC", "https://censec.org.br/", "Escrituras, procurações, testamentos e inventários lavrados "
           "em cartório", "login"),
        _f("SIGEF (Incra)", "https://sigef.incra.gov.br/consultar/parcelas/", "Imóveis rurais certificados, "
           "por nome, CPF ou CNPJ do detentor"),
        _f("SNCR: imóveis rurais", "https://sncr.serpro.gov.br/sncr-web/consultaPublica.jsf", "Cadastro "
           "rural e CCIR"),
        _f("ANAC: aeronaves (RAB)", "https://sistemas.anac.gov.br/aeronaves/cons_rab.asp", "Proprietário e "
           "operador de aeronave pela matrícula"),
        _f("Placa: modelo e FIPE", "https://placafipe.com/placa/{q}", "Marca, modelo, ano, cor, cidade e "
           "valor FIPE pela placa"),
        _f("PNCP: contratos públicos", "https://pncp.gov.br/app/contratos?q={q}", "Contratos e licitações em "
           "que a empresa aparece"),
    ]),
    ("Telefone", "📱", [
        _f("BigDataCorp: dono do telefone", _BDC, "Pessoas e empresas com o número no cadastro, com CPF ou "
           "CNPJ, outros contatos e endereços", "pago", "auto"),
        _f("ABR Telecom: operadora atual", "https://consultanumero.abrtelecom.com.br/consultanumero/consulta/"
           "consultaSituacaoAtualCtg", "Operadora de hoje, já com a portabilidade. Exige captcha"),
        _f("WhatsApp", "https://wa.me/55{d}", "Abre a conversa: foto, nome de exibição e conta comercial"),
        _f("Telegram", "https://t.me/+55{d}", "Abre o perfil, se o número estiver visível"),
        _f("Truecaller", "https://www.truecaller.com/search/br/{d}", "Nome como aparece na agenda de terceiros",
           "login"),
        _f("Sync.me", "https://sync.me/search/?number=55{d}", "Nome e foto vindos de agendas", "login"),
        _f("Google: número exato", "https://www.google.com/search?q=%22{q}%22", "Anúncios, cadastros e "
           "páginas que citam o número"),
    ]),
    ("E-mail", "✉️", [
        _f("BigDataCorp: dono do e-mail", _BDC, "Pessoas e empresas com o e-mail no cadastro", "pago", "auto"),
        _f("Holehe", "https://github.com/megadose/holehe", "Em quais sites o e-mail tem conta", "gratis", "auto"),
        _f("Hudson Rock", "https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email={q}",
           "Se o e-mail aparece em máquina infectada por ladrão de senha", "gratis", "auto",
           "teste@example.com"),
        _f("Epieos", "https://epieos.com/?q={q}", "Conta Google, avaliações no Maps e serviços ligados",
           "login"),
        _f("Have I Been Pwned", "https://haveibeenpwned.com/account/{q}", "Vazamentos em que o e-mail aparece"),
        _f("Intelligence X", "https://intelx.io/?s={q}", "Vazamentos, pastes e dark web", "login"),
        _f("DeHashed", "https://dehashed.com/search?query={q}", "Registros de vazamento com os campos", "pago"),
    ]),
    ("Usuário e redes sociais", "🧑‍💻", [
        _f("WhatsMyName", "https://whatsmyname.app/?q={q}", "Mesmo usuário em centenas de sites",
           "gratis", "auto"),
        _f("Coletores de LinkedIn e Instagram", "https://brightdata.com/products/web-scraper", "Perfil "
           "completo sem login, pela Bright Data", "pago", "auto"),
        _f("Instagram", "https://www.instagram.com/{q}/", "Perfil pelo nome de usuário", "login"),
        _f("X (Twitter)", "https://x.com/{q}", "Perfil pelo nome de usuário", "login"),
        _f("TikTok", "https://www.tiktok.com/@{q}", "Perfil pelo nome de usuário"),
        _f("GitHub", "https://github.com/{q}", "Perfil, repositórios e e-mail de commit"),
        _f("Telegram", "https://t.me/{q}", "Perfil, canal ou grupo pelo nome de usuário"),
        _f("LinkedIn pelo Google", "https://www.google.com/search?q=site%3Alinkedin.com%2Fin+%22{q}%22",
           "Perfis públicos pelo nome, sem login"),
        _f("Facebook pelo Google", "https://www.google.com/search?q=site%3Afacebook.com+%22{q}%22",
           "Perfis e páginas pelo nome"),
    ]),
    ("Domínio, site e IP", "🌐", [
        _f("Registro.br: titular", "https://registro.br/tecnologia/ferramentas/whois/?search={q}",
           "Dono do domínio .br, com CPF ou CNPJ", "gratis", "auto"),
        _f("crt.sh", "https://crt.sh/?q={q}", "Todos os subdomínios que já tiveram certificado",
           "gratis", "auto"),
        _f("urlscan.io", "https://urlscan.io/search/#{q}", "Capturas do site, requisições e domínios vizinhos"),
        _f("VirusTotal", "https://www.virustotal.com/gui/search/{q}", "Reputação, DNS passivo e arquivos "
           "ligados"),
        _f("Shodan", "https://www.shodan.io/search?query={q}", "Portas e serviços expostos", "login"),
        _f("ViewDNS: whois reverso", "https://viewdns.info/reversewhois/?q={q}", "Outros domínios do mesmo "
           "dono ou e-mail"),
        _f("BuiltWith", "https://builtwith.com/{q}", "Tecnologias e identificadores de analytics em comum"),
        _f("Wayback Machine", "https://web.archive.org/web/*/{q}", "Versões antigas do site"),
        _f("IPinfo", "https://ipinfo.io/{q}", "Provedor, cidade e tipo de rede do IP", exemplo="8.8.8.8"),
    ]),
    ("Imagem e localização", "📷", [
        _f("Google Lens", "https://lens.google.com/", "Busca reversa de imagem e de objetos"),
        _f("Yandex Imagens", "https://yandex.com/images/", "A melhor busca reversa de rosto entre as gratuitas"),
        _f("TinEye", "https://tineye.com/", "Onde a imagem apareceu primeiro"),
        _f("PimEyes", "https://pimeyes.com/", "Busca de rosto na web aberta", "pago"),
        _f("FaceCheck.ID", "https://facecheck.id/", "Busca de rosto em redes sociais e notícias", "pago"),
        _f("Forensically", "https://29a.ch/photo-forensics/", "Sinais de edição e metadados da imagem"),
        _f("SunCalc", "https://www.suncalc.org/", "Hora da foto pela sombra"),
    ]),
    ("Sanções, PEP e vazamentos societários", "🚩", [
        _f("OpenSanctions", "https://www.opensanctions.org/search/?q={q}", "Sanções e PEP do mundo todo",
           "gratis", "auto"),
        _f("ICIJ Offshore Leaks", "https://offshoreleaks.icij.org/search?q={q}", "Offshores dos Panama, "
           "Paradise e Pandora Papers"),
        _f("OCCRP Aleph", "https://aleph.occrp.org/search?q={q}", "Documentos e registros de investigações "
           "jornalísticas", "login"),
        _f("OFAC (Tesouro dos EUA)", "https://sanctionssearch.ofac.treas.gov/", "Lista de sanções dos "
           "Estados Unidos"),
        _f("Interpol: difusões vermelhas", "https://www.interpol.int/How-we-work/Notices/Red-Notices/"
           "View-Red-Notices", "Procurados internacionais"),
    ]),
    ("Criptoativos", "🪙", [
        _f("Blockchair", "https://blockchair.com/search?q={q}", "Endereço ou transação em várias redes"),
        _f("Etherscan", "https://etherscan.io/search?q={q}", "Saldo, tokens e histórico na Ethereum"),
        _f("Chainabuse", "https://www.chainabuse.com/", "Denúncias de golpe ligadas a um endereço"),
        _f("Arkham", "https://intel.arkm.com/", "Carteiras identificadas e fluxo entre entidades", "login"),
    ]),
    ("Dados contratáveis no Brasil", "💳", [
        _f("BigDataCorp", "https://bigdatacorp.com.br/", "Já contratada e integrada: CPF, CNPJ, telefone, "
           "e-mail, nome, processos, veículos", "pago", "auto"),
        _f("Infosimples", "https://infosimples.com/consultas/", "Automatiza centenas de consultas oficiais: "
           "Detran, Receita, protestos, tribunais, certidões", "pago", "api"),
        _f("Escavador API", "https://api.escavador.com/", "Processos por nome ou documento e monitoramento "
           "de diários", "pago", "api"),
        _f("Judit", "https://judit.io/", "Processos por CPF, CNPJ, OAB ou nome, com monitoramento",
           "pago", "api"),
        _f("Assertiva", "https://assertivasolucoes.com.br/", "Localização: telefone, e-mail e endereço "
           "atualizados por CPF ou CNPJ", "pago", "api"),
        _f("Direct Data", "https://www.directd.com.br/", "Cadastro, veículos por placa, score e certidões",
           "pago", "api"),
        _f("CNPJá", "https://cnpja.com/", "CNPJ em tempo real na Receita, Simples, Sintegra e Suframa",
           "pago", "api"),
    ]),
    ("Ferramentas de código aberto", "🧰", [
        _f("Maigret", "https://github.com/soxoj/maigret", "Usuário em mais de 3.000 sites, com extração de "
           "dados do perfil", "gratis", "auto"),
        _f("Sherlock", "https://github.com/sherlock-project/sherlock", "Usuário em centenas de redes",
           "gratis", "codigo"),
        _f("Blackbird", "https://github.com/p1ngul1n0/blackbird", "Usuário e e-mail em redes, com relatório",
           "gratis", "codigo"),
        _f("GHunt", "https://github.com/mxrch/GHunt", "Conta Google por trás de um e-mail", "gratis", "codigo"),
        _f("Ignorant", "https://github.com/megadose/ignorant", "Em quais sites um telefone tem conta",
           "gratis", "codigo"),
        _f("PhoneInfoga", "https://github.com/sundowndev/phoneinfoga", "Varredura de número de telefone",
           "gratis", "codigo"),
        _f("SpiderFoot", "https://github.com/smicallef/spiderfoot", "Automação com mais de 200 módulos",
           "gratis", "codigo"),
        _f("theHarvester", "https://github.com/laramies/theHarvester", "E-mails, subdomínios e nomes de "
           "uma organização", "gratis", "codigo"),
        _f("Rede CNPJ", "https://github.com/rictom/rede-cnpj", "Grafo de sócios e empresas sobre a base "
           "da Receita", "gratis", "codigo"),
        _f("Querido Diário", "https://github.com/okfn-brasil/querido-diario", "Raspadores dos diários "
           "oficiais municipais", "gratis", "auto"),
        _f("Robin", "https://github.com/apurvsinghgautam/robin", "Busca na dark web com relatório por IA. "
           "Roda na página Dark web", "gratis", "auto"),
        _f("OSINT Brazuca", "https://github.com/osintbrazuca/osint-brazuca", "Lista de fontes brasileiras "
           "mantida pela comunidade", "gratis", "codigo"),
        _f("Awesome OSINT", "https://github.com/jivoi/awesome-osint", "Lista internacional de referência",
           "gratis", "codigo"),
    ]),
]

SO_ORDEM_JUDICIAL = (
    "Saldo e bloqueio de contas (SISBAJUD), restrição de veículos (RENAJUD), declaração de renda "
    "(INFOJUD), imóveis em todo o país (SREI/CNIB) e titular de chave Pix não são consulta aberta: "
    "saem por ordem judicial, pedida no processo."
)


def todas() -> list[Fonte]:
    return [f for _, _, fontes in DIRETORIO for f in fontes]


def resumo() -> dict:
    fontes = todas()
    return {
        "total": len(fontes),
        "categorias": len(DIRETORIO),
        "automaticas": sum(f.acesso == "auto" for f in fontes),
        "gratuitas": sum(f.custo == "gratis" for f in fontes),
    }


def filtrar(texto: str = "", custo: str = "", so_com_dado: bool = False) -> list[tuple[str, str, list[Fonte]]]:
    """Recorte da árvore: por texto livre, por custo e por fonte que abre já pesquisada."""
    alvo = (texto or "").strip().lower()
    saida = []
    for nome, icone, fontes in DIRETORIO:
        escolhidas = [
            f for f in fontes
            if (not alvo or alvo in f"{nome} {f.nome} {f.entrega}".lower())
            and (not custo or f.custo == custo)
            and (not so_com_dado or f.aceita_dado)
        ]
        if escolhidas:
            saida.append((nome, icone, escolhidas))
    return saida
