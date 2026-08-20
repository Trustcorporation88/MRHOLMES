"""Relatório PDF, análise de foto (EXIF) e monitoramento. Sem rede."""

from __future__ import annotations

import io
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holmes import monitor, photo, report_pdf  # noqa: E402
from holmes.dossier import Dossier  # noqa: E402
from holmes.entity import detect  # noqa: E402
from holmes.findings import ConnectorResult, Confidence, Finding, FindingKind  # noqa: E402


def _dossie(alvo="Fulano de Tal", findings=None):
    d = Dossier(entity=detect(alvo))
    d.add_results([ConnectorResult("r", "R", True, findings or [
        Finding(FindingKind.EMAIL, "x@y.com", "r", confidence=Confidence.CONFIRMED),
    ])])
    d.consolidate()
    return d


# ── PDF ──────────────────────────────────────────────────────────────────────

def test_pdf_gera_bytes_validos():
    d = _dossie()
    d.summary = "Leitura do caso de teste."
    d.next_steps = ["passo 1", "passo 2"]
    pdf = report_pdf.generate(d)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 800


def test_pdf_escapa_html_perigoso():
    d = _dossie(findings=[Finding(FindingKind.NOTE, "<script>x</script>", "r")])
    # Não deve levantar exceção com caracteres especiais.
    assert report_pdf.generate(d).startswith(b"%PDF")


# ── foto / EXIF ──────────────────────────────────────────────────────────────

def _jpeg_simples() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (12, 8), "blue").save(buf, "JPEG")
    return buf.getvalue()


def test_foto_sem_exif_avisa():
    info = photo.analisar_bytes(_jpeg_simples())
    assert info["dimensoes"] == "12×8"
    assert info["aviso"]  # sem EXIF → aviso
    assert info["gps"] is None


def test_foto_arquivo_invalido_nao_quebra():
    info = photo.analisar_bytes(b"isto nao e imagem")
    assert info["aviso"]
    assert info["tem_exif"] is False


def test_dms_para_graus_hemisferio_sul():
    # 23°33'S deve virar negativo.
    g = photo._dms_para_graus(((23, 1), (33, 1), (0, 1)), "S")
    assert g is not None and g < 0
    assert abs(g + 23.55) < 0.01


def test_resumo_texto_monta_linhas():
    info = {"camera": "Apple iPhone", "datas": ["DateTime: 2024"],
            "dimensoes": "100×100", "gps": {"lat": -23.5, "lon": -46.6,
            "maps": "https://maps.google.com/?q=-23.5,-46.6"}, "software": None}
    linhas = photo.resumo_texto(info)
    assert any("iPhone" in l for l in linhas)
    assert any("GPS" in l for l in linhas)


# ── monitoramento ────────────────────────────────────────────────────────────

def _mon_temp(monkeypatch):
    base = pathlib.Path(tempfile.mkdtemp())
    monkeypatch.setattr(monitor, "WATCH_DIR", base)
    monkeypatch.setattr(monitor, "WATCH_FILE", base / "_watchlist.json")
    monkeypatch.setattr(monitor, "ALERTS_FILE", base / "_alerts.json")
    from holmes import history
    monkeypatch.setattr(history, "HISTORY_DIR", base / "hist")


def test_add_remove_watchlist(monkeypatch):
    _mon_temp(monkeypatch)
    assert monitor.add_target("Alvo Um")
    assert not monitor.add_target("Alvo Um")   # duplicado
    assert not monitor.add_target("")          # vazio
    assert len(monitor.watchlist()) == 1
    monitor.remove_target("Alvo Um")
    assert monitor.watchlist() == []


def test_run_once_gera_alerta_na_novidade(monkeypatch):
    _mon_temp(monkeypatch)
    monitor.add_target("Alvo X")
    chamada = {"n": 0}

    def fake_inv(alvo, cfg=None):
        chamada["n"] += 1
        finds = [Finding(FindingKind.EMAIL, "a@b.com", "r")]
        if chamada["n"] > 1:
            finds.append(Finding(FindingKind.PHONE, "+5511999998888", "r"))
        d = Dossier(entity=detect(alvo))
        d.add_results([ConnectorResult("r", "R", True, finds)])
        d.consolidate()
        return d

    # 1ª rodada: baseline, sem alerta (nada com que comparar).
    assert monitor.run_once(fake_inv, config=None) == []
    # 2ª rodada: telefone novo → alerta.
    novos = monitor.run_once(fake_inv, config=None)
    assert len(novos) == 1
    assert "Telefones" in novos[0]["texto"]
    assert monitor.unread_count() == 1


def test_marcar_lidos(monkeypatch):
    _mon_temp(monkeypatch)
    monitor._push_alert({"alvo": "x", "quando": 0, "tipo": "novidade",
                         "texto": "t", "lido": False})
    assert monitor.unread_count() == 1
    monitor.marcar_lidos()
    assert monitor.unread_count() == 0


def test_run_once_isola_erro_de_alvo(monkeypatch):
    _mon_temp(monkeypatch)
    monitor.add_target("Quebra")

    def inv_quebra(alvo, cfg=None):
        raise RuntimeError("fonte fora do ar")

    monitor.run_once(inv_quebra, config=None)
    alertas = monitor.alerts()
    assert alertas and alertas[0]["tipo"] == "erro"
