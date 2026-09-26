"""Funções puras de ``deploy/smoke_modelos.py`` (FR-021, AC-12, constituição VII).

Escolha do modelo, erro resumido sem segredo, leitura da chave direto para a
memória e atualização do ``env.example``. Sem rede e sem SDK do Gemini.

Adaptado da branch ``alt/000-fundacao-contratos-claude`` (João Paulo).
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

RAIZ_REPO = Path(__file__).resolve().parents[3]
CHAVE = "AIza" + "B" * 35


def _carregar() -> ModuleType:
    caminho = RAIZ_REPO / "deploy" / "smoke_modelos.py"
    spec = importlib.util.spec_from_file_location("bussola_deploy_smoke_modelos", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


sm = _carregar()


def _tentativa(tipo: str, modelo: str, ok: bool, local: str = "us-central1", **extra):
    return sm.Tentativa(tipo=tipo, modelo=modelo, via=sm.VIA_VERTEX, local=local, ok=ok, **extra)


def test_escolher_devolve_a_primeira_tentativa_ok_do_tipo():
    tentativas = [
        _tentativa("flash", "flash-a", False, detalhe="404"),
        _tentativa("embedding", "emb-a", True, dimensao=768),
        _tentativa("flash", "flash-b", True, local="global"),
        _tentativa("flash", "flash-c", True),
    ]
    assert sm.escolher(tentativas, "flash").modelo == "flash-b"
    assert sm.escolher(tentativas, "embedding").modelo == "emb-a"


def test_escolher_sem_sucesso_devolve_none():
    assert sm.escolher([_tentativa("flash", "flash-a", False)], "flash") is None
    assert sm.escolher([], "embedding") is None


def test_resumo_de_erro_oculta_a_chave_e_cabe_na_tabela():
    erro = RuntimeError(f"falhou com a chave {CHAVE} | detalhe\n" + "x" * 500)
    resumo = sm._resumo_erro(erro, ocultar=(CHAVE, ""))
    assert CHAVE not in resumo
    assert "***" in resumo
    assert "|" not in resumo
    assert "\n" not in resumo
    assert len(resumo) <= 160


def test_resumo_de_erro_da_api_usa_codigo_e_status():
    erro = SimpleNamespace(code=404, status="NOT_FOUND", message="modelo não encontrado")
    assert sm._resumo_erro(erro).startswith("404 NOT_FOUND: modelo não encontrado")


def test_chave_do_secret_manager_vai_para_a_memoria_e_nunca_e_impressa(monkeypatch, capsys):
    pedidos = []

    def falso(comando, **kwargs):
        pedidos.append((comando, kwargs))
        return SimpleNamespace(returncode=0, stdout=CHAVE + "\n", stderr="")

    monkeypatch.setattr(sm.subprocess, "run", falso)
    chave, erro = sm.ler_chave_gemini("meu-projeto")
    saida = capsys.readouterr()
    assert (chave, erro) == (CHAVE, "")
    assert CHAVE not in saida.out + saida.err
    comando, kwargs = pedidos[0]
    assert kwargs.get("capture_output") is True
    assert f"--secret={sm.SEGREDO_GEMINI}" in comando


def test_falha_ao_ler_a_chave_devolve_so_a_primeira_linha_do_erro(monkeypatch):
    def falso(comando, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="PERMISSION_DENIED\nlinha 2")

    monkeypatch.setattr(sm.subprocess, "run", falso)
    chave, erro = sm.ler_chave_gemini("meu-projeto")
    assert chave is None
    assert "PERMISSION_DENIED" in erro
    assert "linha 2" not in erro


def test_atualizar_env_example_troca_so_os_modelos(monkeypatch, tmp_path):
    env = tmp_path / "env.example"
    env.write_text(
        "# comentário\nBUSSOLA_MODEL=antigo\nEMBEDDING_MODEL=antigo\nGOOGLE_API_KEY=\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sm, "ENV_EXAMPLE", env)
    mudancas = sm.atualizar_env_example(
        _tentativa("flash", "flash-b", True), _tentativa("embedding", "emb-y", True)
    )
    assert mudancas == ["BUSSOLA_MODEL=flash-b", "EMBEDDING_MODEL=emb-y"]
    assert env.read_text(encoding="utf-8") == (
        "# comentário\nBUSSOLA_MODEL=flash-b\nEMBEDDING_MODEL=emb-y\nGOOGLE_API_KEY=\n"
    )
    assert sm.atualizar_env_example(_tentativa("flash", "flash-b", True), None) == []


def test_relatorio_registra_local_do_flash_e_dimensao_sem_segredo():
    args = SimpleNamespace(projeto="batalha-time-07-lkbv", locais="us-central1,global")
    tentativas = [
        _tentativa("flash", "flash-a", False, detalhe="404 NOT_FOUND"),
        _tentativa("flash", "flash-b", True, local="global", latencia_ms=12),
        _tentativa("embedding", "emb-y", True, latencia_ms=30, dimensao=768),
    ]
    md = sm.montar_relatorio(args, [], tentativas, [])
    for esperado in ("`flash-b`", "`emb-y`", "768", "BUSSOLA_LOCAL_MODELO=global", "404 NOT_FOUND"):
        assert esperado in md
    assert "AIza" not in md
