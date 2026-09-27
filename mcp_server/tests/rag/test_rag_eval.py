"""Eval do RAG (``eval/rag/``) rodado offline: perguntas, top-3 e negativos.

O backend numpy usa o cache versionado de embeddings das perguntas
(``eval/rag/embeddings_perguntas.npz``, mesmo modelo do índice), então o
resultado é reprodutível sem rede.
"""

from pathlib import Path

import pytest

from bussola_mcp.contratos import contem_taxa
from bussola_mcp.rag.index import INDEX_DIR, load_chunks


@pytest.fixture(scope="module")
def eval_set(rodar_eval):
    return rodar_eval.load_eval_set()


@pytest.fixture(scope="module")
def run(rodar_eval, eval_set):
    return rodar_eval.run_eval(eval_set)


def _report(run, backend: str):
    return next(r for r in run.reports if r.backend == backend)


def test_conjunto_tem_o_minimo_pedido(eval_set) -> None:
    assert eval_set.k == 3
    assert len(eval_set.questions) >= 10
    products = [q for q in eval_set.questions if q.kind == "produto"]
    assert len(products) >= 2
    entrada = next(q for q in products if "entrada" in q.text.lower())
    assert entrada.expected == ("cofrinhos#1",)
    assert any(n.text == "previsão do tempo" for n in eval_set.negatives)


def test_esperados_existem_no_indice(eval_set) -> None:
    indexed = {c.trecho_id for c in load_chunks(INDEX_DIR)}
    for question in eval_set.questions:
        assert set(question.expected) <= indexed, question.id


def test_numpy_atinge_a_meta_de_top3(run, rodar_eval) -> None:
    assert run.numpy_status.startswith("ok (gemini-embedding-001, dim 768)")
    numpy_report = _report(run, "numpy")
    assert numpy_report.hit_rate() >= rodar_eval.TARGET_HIT_RATE
    assert numpy_report.hit_rate("produto") == 1.0


def test_lexico_e_a_linha_de_base(run) -> None:
    lexical = _report(run, "lexico")
    assert lexical.hit_rate() >= 0.75
    assert lexical.hit_rate("produto") == 1.0


@pytest.mark.parametrize("backend", ["lexico", "numpy"])
def test_negativos_nao_trazem_trecho(run, backend: str) -> None:
    report = _report(run, backend)
    assert report.negatives_ok
    assert all(n.returned == 0 for n in report.negatives)


def test_limiar_numpy_separa_negativos_de_acertos(run) -> None:
    assert run.calibration is not None
    positives, negatives = run.calibration
    min_first_hit = min(score for _, score in positives if score is not None)
    max_negative = max(score for _, score in negatives)
    assert max_negative < run.min_score < min_first_hit


def test_nenhum_trecho_de_produto_com_taxa(run) -> None:
    assert run.rate_violations == []
    products = [c for c in load_chunks(INDEX_DIR) if c.tema.value == "produto"]
    assert products and not any(contem_taxa(c.texto) for c in products)


def test_resultados_versionados_estao_em_dia(run, rodar_eval) -> None:
    """Falha se ``eval/rag/RESULTADOS.md`` não foi regenerado (``make eval-rag``)."""
    committed = (rodar_eval.EVAL_DIR / "RESULTADOS.md").read_text(encoding="utf-8")
    assert committed == rodar_eval.render_markdown(run)


def test_cli_grava_o_relatorio(rodar_eval, tmp_path: Path, capsys) -> None:
    out = tmp_path / "RESULTADOS.md"
    assert rodar_eval.main(["--resultados", str(out)]) == 0
    assert "numpy: " in capsys.readouterr().out
    assert "previsão do tempo" in out.read_text(encoding="utf-8")


def test_cache_de_perguntas_so_responde_retrieval_query(rodar_eval, eval_set) -> None:
    cache = rodar_eval.load_query_cache()
    assert cache is not None and cache.knows(eval_set.texts)
    with pytest.raises(Exception) as caught:
        cache.embed(["pergunta que não está no cache"], "RETRIEVAL_QUERY")
    assert type(caught.value).__name__ == "EmbeddingUnavailableError"
