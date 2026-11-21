"""Leitura do cenário da foto por IA. Sem rede: o provedor é simulado."""

import io
import json
from unittest import mock

from PIL import Image

from holmes import foto_ia

RESPOSTA = {
    "resumo": "Rua comercial com sobrados e um letreiro de farmácia.",
    "ambiente": "externo",
    "pistas": [
        {"tipo": "texto", "observado": "Letreiro 'Farmácia São João'", "indica": "rede de farmácias brasileira",
         "confianca": "alta"},
        {"tipo": "vegetação", "observado": "palmeiras imperiais", "indica": "clima tropical", "confianca": "Média"},
        {"tipo": "outro", "observado": "", "indica": ""},
    ],
    "textos_visiveis": ["Farmácia São João", "ABC-1D23", "Rua das [parcial]"],
    "local_provavel": {"pais": "Brasil", "regiao": "SP", "cidade": "Campinas", "ponto": None,
                       "confianca": "média", "motivo": "letreiro e arquitetura"},
    "como_confirmar": ["Procurar a farmácia no Street View"],
    "limites": ["foto sem ponto de referência famoso"],
}


def _jpeg(lado: int = 64, formato: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (lado, lado // 2), (120, 140, 90)).save(buf, formato)
    return buf.getvalue()


def _resp(corpo: dict | None = None, status: int = 200):
    r = mock.Mock(status_code=status)
    r.json.return_value = corpo if corpo is not None else {"content": [{"type": "text", "text": json.dumps(RESPOSTA)}]}
    return r


def test_regras_do_prompt_proibem_identificar_pessoas():
    assert "Nunca identifique pessoas pelo rosto" in foto_ia.SISTEMA
    assert "Nunca invente nome de rua" in foto_ia.SISTEMA
    assert "\\n" not in foto_ia.SISTEMA  # barra invertida literal estragaria o prompt


def test_imagem_e_reduzida_convertida_e_sem_exif():
    from PIL import Image as I

    ex = I.Exif()
    ex[0x010F] = "Apple"
    buf = io.BytesIO()
    I.new("RGB", (4000, 3000), (10, 20, 30)).save(buf, "PNG")
    jpeg = foto_ia.preparar_imagem(buf.getvalue())
    img = I.open(io.BytesIO(jpeg))
    assert img.format == "JPEG" and max(img.size) == foto_ia.LADO_MAXIMO and not img.getexif()


def test_envia_a_imagem_ao_modelo_e_normaliza_a_resposta():
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": ""}), \
         mock.patch.object(foto_ia.requests, "post", return_value=_resp()) as post:
        analise, erro = foto_ia.analisar_cenario(_jpeg(2000))
    assert erro == "" and analise["resumo"].startswith("Rua comercial")
    corpo = post.call_args.kwargs["json"]
    bloco = corpo["messages"][0]["content"][0]
    assert bloco["type"] == "image" and bloco["source"]["media_type"] == "image/jpeg"
    assert corpo["system"] == foto_ia.SISTEMA
    # normalização: confiança com acento vira sem acento, pista vazia some
    assert analise["local_provavel"]["confianca"] == "media"
    assert [p["confianca"] for p in analise["pistas"]] == ["alta", "media"]
    assert analise["local_provavel"]["ponto"] is None


def test_modelo_inexistente_passa_para_o_proximo_e_erro_comum_encerra():
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "", "HOLMES_VISAO_MODELO": ""}), \
         mock.patch.object(foto_ia.requests, "post", side_effect=[_resp({}, 404), _resp()]) as post:
        analise, _ = foto_ia.analisar_cenario(_jpeg())
    assert analise and post.call_count == 2
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": ""}), \
         mock.patch.object(foto_ia.requests, "post", return_value=_resp({}, 500)) as post:
        analise, erro = foto_ia.analisar_cenario(_jpeg())
    assert analise is None and "legível" in erro and post.call_count == 1


def test_chave_recusada_aparece_com_a_causa_e_a_openai_assume():
    # Anthropic recusa a chave (401): a mensagem diz isso, sem fingir que a resposta veio ilegível
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "velha", "OPENAI_API_KEY": ""}), \
         mock.patch.object(foto_ia.requests, "post", return_value=_resp({}, 401)):
        analise, erro = foto_ia.analisar_cenario(_jpeg())
    assert analise is None and "chave da Anthropic foi recusada" in erro and "Railway" in erro
    # com chave da OpenAI valida, ela responde no lugar
    openai_ok = _resp({"choices": [{"message": {"content": json.dumps(RESPOSTA)}}]})
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "velha", "OPENAI_API_KEY": "nova"}), \
         mock.patch.object(foto_ia.requests, "post", side_effect=[_resp({}, 401), openai_ok]) as post:
        analise, erro = foto_ia.analisar_cenario(_jpeg())
    assert erro == "" and analise["resumo"].startswith("Rua comercial") and post.call_count == 2
    # sem credito ou limite: 429 tambem explica
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": ""}), \
         mock.patch.object(foto_ia.requests, "post", return_value=_resp({}, 429)):
        assert "limitou" in foto_ia.analisar_cenario(_jpeg())[1]


def test_sem_chave_arquivo_invalido_e_json_quebrado():
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}):
        assert "Sem chave" in foto_ia.analisar_cenario(_jpeg())[1]
    with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": ""}):
        assert "não é uma imagem" in foto_ia.analisar_cenario(b"nao e foto")[1]
        quebrado = _resp({"content": [{"type": "text", "text": "não consegui"}]})
        with mock.patch.object(foto_ia.requests, "post", return_value=quebrado):
            assert "legível" in foto_ia.analisar_cenario(_jpeg())[1]


def test_json_com_cerca_de_codigo_e_lido():
    assert foto_ia._json_de("```json\n{\"a\": 1}\n```") == {"a": 1}
    assert foto_ia._json_de("sem json") is None


def test_placas_e_link_do_mapa():
    assert foto_ia.placas_no_texto(["ABC-1D23", "abc 1234", "Farmácia", "ABC1D23"]) == ["ABC1D23", "ABC1234"]
    local = {"cidade": "Campinas", "regiao": "SP", "pais": "Brasil", "ponto": None, "confianca": "media"}
    assert foto_ia.link_do_mapa(local).endswith("query=Campinas%2C+SP%2C+Brasil")
    assert foto_ia.link_do_mapa({**local, "confianca": "nenhuma"}) is None
    assert foto_ia.link_do_mapa({"cidade": None, "ponto": None, "confianca": "alta"}) is None


def test_tela_mostra_local_pistas_textos_e_placa_depois_do_clique():
    from streamlit.testing.v1 import AppTest

    def app():
        import holmes_ui

        holmes_ui._render_cenario_ia(b"foto-qualquer")

    analise = foto_ia.normalizar(RESPOSTA)
    with mock.patch.object(foto_ia, "disponivel", return_value=True), \
         mock.patch.object(foto_ia, "analisar_cenario", return_value=(analise, "")):
        at = AppTest.from_function(app, default_timeout=60).run()
        assert not at.exception and at.button(key="foto_ia_btn")
        at.button(key="foto_ia_btn").click().run()
    assert not at.exception
    texto = " ".join(m.value for m in at.markdown)
    assert "Local provável:" in texto and "Campinas" in texto and "confiança **media**" in texto
    assert "Farmácia São João" in texto
    assert [c.value for c in at.code] == ["ABC1D23"]
    assert any("Limites" in c.value for c in at.caption)
