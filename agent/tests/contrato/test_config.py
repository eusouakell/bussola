"""Fonte única de configuração (:mod:`bussola_agent.config`).

Cobre o contrato do módulo: default explícito por variável, leitura no momento
do uso (e não no import), ``env`` injetável, nenhum segredo e os nomes de
variável iguais aos de ``contracts/env.example``.
"""

import re
from pathlib import Path

import pytest

from bussola_agent import config

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / "contracts" / "env.example"

# Variável de ambiente → (acessor, valor default esperado).
VARIAVEIS: dict[str, tuple[str, object]] = {
    "MCP_URL": ("mcp_url", config.MCP_URL_PADRAO),
    "MCP_USE_OIDC": ("mcp_use_oidc", False),
    "BUSSOLA_MODEL": ("modelo_principal", config.MODELO_PADRAO),
    "GOOGLE_CLOUD_PROJECT": ("projeto_gcp", ""),
    "BQ_DATASET_APP": ("dataset_app", config.DATASET_APP_PADRAO),
    "BUSSOLA_FAKES": ("fakes_habilitados", True),
    "MODEL_ARMOR_TEMPLATE": ("template_model_armor", ""),
    "ANCHOR_USER_ID": ("anchor_user_id", config.ANCHOR_USER_ID_PADRAO),
    "REPLAY_START_ANOMES": ("replay_start_anomes", config.REPLAY_START_PADRAO),
    "LOG_LEVEL": ("nivel_de_log", "INFO"),
}


def test_ambiente_vazio_devolve_o_default_de_cada_variavel() -> None:
    """Sem nenhuma variável setada, tudo funciona (modo fake é o padrão)."""
    for _, (acessor, padrao) in VARIAVEIS.items():
        assert getattr(config, acessor)(env={}) == padrao
    assert config.fakes_habilitados(env={}) is True


@pytest.mark.parametrize(("variavel", "acessor"), [(v, a) for v, (a, _) in VARIAVEIS.items()])
def test_cada_acessor_le_a_sua_variavel(
    monkeypatch: pytest.MonkeyPatch, variavel: str, acessor: str
) -> None:
    """A leitura acontece na chamada: ``monkeypatch.setenv`` depois do import vale."""
    valor = "202511" if variavel == "REPLAY_START_ANOMES" else "TRUE"
    monkeypatch.setenv(variavel, valor)
    obtido = getattr(config, acessor)()
    esperado: object = 202511 if variavel == "REPLAY_START_ANOMES" else "TRUE"
    if variavel in ("MCP_USE_OIDC", "BUSSOLA_FAKES"):
        esperado = True
    assert obtido == esperado


def test_env_injetado_tem_prioridade_sobre_o_processo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BQ_DATASET_APP", "do_processo")
    assert config.dataset_app(env={"BQ_DATASET_APP": "injetado"}) == "injetado"
    assert config.dataset_app() == "do_processo"


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("TRUE", True),
        ("true", True),
        ("", True),
        ("qualquer", True),
        ("FALSE", False),
        ("0", False),
    ],
)
def test_fakes_habilitados_desliga_so_com_valor_explicito(valor: str, esperado: bool) -> None:
    assert config.fakes_habilitados({"BUSSOLA_FAKES": valor}) is esperado


@pytest.mark.parametrize(
    ("valor", "esperado"), [("TRUE", True), ("true", True), ("FALSE", False), ("qualquer", False)]
)
def test_mcp_use_oidc_liga_so_com_true(valor: str, esperado: bool) -> None:
    assert config.mcp_use_oidc(env={"MCP_USE_OIDC": valor}) is esperado


def test_o_argumento_tem_prioridade_sobre_o_ambiente() -> None:
    assert config.mcp_url("http://x/mcp", env={"MCP_URL": "http://y/mcp"}) == "http://x/mcp"
    assert config.mcp_use_oidc(True, env={"MCP_USE_OIDC": "FALSE"}) is True


def test_cadeia_de_modelos_poe_o_principal_na_frente_sem_repetir() -> None:
    assert config.cadeia_de_modelos("gemini-3.5-flash") == (
        "gemini-3.5-flash",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
    )
    assert config.cadeia_de_modelos(env={}) == config.MODELOS_FLASH
    assert config.cadeia_de_modelos("outro-modelo")[0] == "outro-modelo"
    assert len(set(config.cadeia_de_modelos("gemini-3.8-flash"))) == len(config.MODELOS_FLASH)


def test_replay_start_invalido_levanta() -> None:
    with pytest.raises(ValueError):
        config.replay_start_anomes(env={"REPLAY_START_ANOMES": "junho"})


def test_os_nomes_das_variaveis_existem_no_env_example() -> None:
    """Nenhum nome inventado: todos aparecem em ``contracts/env.example`` (§7)."""
    texto = ENV_EXAMPLE.read_text(encoding="utf-8")
    declarados = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", texto, flags=re.MULTILINE))
    assert set(VARIAVEIS) <= declarados


def test_nenhum_segredo_e_lido_ou_exposto() -> None:
    """Constituição VII: nenhum acessor lê nem devolve segredo do ambiente."""
    sentinela = "NAO-DEVE-SAIR-DAQUI"
    env = {
        "GOOGLE_API_KEY": sentinela,
        "GEMINI_API_KEY": sentinela,
        "GOOGLE_APPLICATION_CREDENTIALS": sentinela,
    }
    for acessor, _ in VARIAVEIS.values():
        assert sentinela not in str(getattr(config, acessor)(env=env))
    # Nenhum nome público que carregaria um segredo (``TTL_TOKEN_OIDC_S`` é prazo, não token).
    suspeito = re.compile(r"api[_-]?key|secret|senha|password|credential|_(KEY|TOKEN)$", re.I)
    publicos = {n for n in dir(config) if not n.startswith("_")}
    assert not {n for n in publicos if suspeito.search(n)}
    # Nenhum default embutido parece credencial.
    literais = [v for n, v in vars(config).items() if not n.startswith("_") and isinstance(v, str)]
    assert not [v for v in literais if re.search(r"AIza|-----BEGIN|api[_-]?key", v, re.IGNORECASE)]


def test_config_nao_importa_framework() -> None:
    """Configuração é stdlib: nada de ADK, genai, BigQuery ou httpx aqui."""
    fonte = Path(config.__file__).read_text(encoding="utf-8")
    importados = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", fonte, flags=re.MULTILINE)
    assert set(importados) == {"os", "collections.abc"}
