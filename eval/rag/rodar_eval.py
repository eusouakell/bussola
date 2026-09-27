"""Avaliação do RAG de conhecimento (ciclo 002): acertos no top-k por backend.

Uso (a partir da raiz do repositório)::

    uv run --project mcp_server python eval/rag/rodar_eval.py
    uv run --project mcp_server python eval/rag/rodar_eval.py --resultados eval/rag/RESULTADOS.md

- ``lexico`` roda sempre, sem rede.
- ``numpy`` roda quando o índice tem embeddings e as perguntas estão no cache
  ``embeddings_perguntas.npz`` (embeddings ``RETRIEVAL_QUERY`` do mesmo modelo
  do manifesto). Assim o eval é reprodutível offline, inclusive no
  ``make test``. Para (re)gerar o cache, passe ``--atualizar-cache`` com a
  chave inline, nunca impressa nem gravada::

      GOOGLE_GENAI_USE_VERTEXAI=FALSE GOOGLE_API_KEY="$(gcloud secrets versions \
          access latest --secret=gemini-api-key --project batalha-time-07-lkbv)" \
          uv run --project mcp_server python eval/rag/rodar_eval.py --atualizar-cache

A calibração mostra, para o numpy, o score do primeiro acerto de cada
pergunta positiva e o maior score de cada negativa, sem limiar. O limiar
(``DEFAULT_MIN_SCORE``) deve ficar entre os dois grupos.
"""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from bussola_mcp.contratos import TemaConhecimento, contem_taxa
from bussola_mcp.dominio.interfaces import BuscadorContexto
from bussola_mcp.rag import BuscadorLexico, BuscadorNumpy
from bussola_mcp.rag.embedding import (
    TASK_QUERY,
    EmbeddingUnavailableError,
    GeminiEmbedder,
    TaskType,
)
from bussola_mcp.rag.index import INDEX_DIR, load_chunks, load_manifest
from bussola_mcp.rag.lexical import DEFAULT_MIN_COVERAGE, DEFAULT_SINGLE_TERM_COVERAGE
from bussola_mcp.rag.vector import DEFAULT_MIN_SCORE

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = EVAL_DIR / "perguntas.yaml"
QUERY_CACHE = EVAL_DIR / "embeddings_perguntas.npz"
TARGET_HIT_RATE = 0.8


@dataclass(frozen=True)
class Question:
    id: str
    kind: str
    text: str
    expected: tuple[str, ...]


@dataclass(frozen=True)
class NegativeQuestion:
    id: str
    text: str


@dataclass(frozen=True)
class EvalSet:
    k: int
    questions: tuple[Question, ...]
    negatives: tuple[NegativeQuestion, ...]

    @property
    def texts(self) -> list[str]:
        return [q.text for q in self.questions] + [n.text for n in self.negatives]


@dataclass(frozen=True)
class QuestionResult:
    question: Question
    top_ids: tuple[str, ...]

    @property
    def rank(self) -> int | None:
        for position, trecho_id in enumerate(self.top_ids, start=1):
            if trecho_id in self.question.expected:
                return position
        return None

    @property
    def hit(self) -> bool:
        return self.rank is not None


@dataclass(frozen=True)
class NegativeResult:
    question: NegativeQuestion
    returned: int
    top_score: float | None


@dataclass
class BackendReport:
    backend: str
    k: int
    results: list[QuestionResult] = field(default_factory=list)
    negatives: list[NegativeResult] = field(default_factory=list)

    def hit_rate(self, kind: str | None = None) -> float:
        selected = [r for r in self.results if kind is None or r.question.kind == kind]
        return sum(r.hit for r in selected) / len(selected) if selected else 0.0

    def hits(self, kind: str | None = None) -> tuple[int, int]:
        selected = [r for r in self.results if kind is None or r.question.kind == kind]
        return sum(r.hit for r in selected), len(selected)

    @property
    def negatives_ok(self) -> bool:
        return all(n.returned == 0 for n in self.negatives)


def load_eval_set(path: Path = QUESTIONS_FILE) -> EvalSet:
    """Lê ``perguntas.yaml`` e confere o formato (ids únicos, esperados não vazios)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = tuple(
        Question(
            id=str(item["id"]),
            kind=str(item["tipo"]),
            text=str(item["pergunta"]),
            expected=tuple(str(e) for e in item["esperados"]),
        )
        for item in raw["perguntas"]
    )
    negatives = tuple(
        NegativeQuestion(id=str(item["id"]), text=str(item["pergunta"]))
        for item in raw.get("negativas", [])
    )
    ids = [q.id for q in questions] + [n.id for n in negatives]
    if len(ids) != len(set(ids)):
        raise ValueError("perguntas.yaml: id repetido")
    if any(not q.expected for q in questions):
        raise ValueError("perguntas.yaml: pergunta sem esperados")
    if any(q.kind not in {"conhecimento", "produto"} for q in questions):
        raise ValueError("perguntas.yaml: tipo deve ser conhecimento ou produto")
    return EvalSet(k=int(raw.get("k", 3)), questions=questions, negatives=negatives)


def evaluate(searcher: BuscadorContexto, eval_set: EvalSet, backend: str) -> BackendReport:
    """Roda cada pergunta sem filtro de tema e mede acertos no top-k."""
    report = BackendReport(backend=backend, k=eval_set.k)
    for question in eval_set.questions:
        found = searcher.buscar(question.text, eval_set.k, None)
        report.results.append(QuestionResult(question, tuple(t.trecho_id for t in found)))
    for negative in eval_set.negatives:
        found = searcher.buscar(negative.text, eval_set.k, None)
        top = found[0].score if found else None
        report.negatives.append(NegativeResult(negative, len(found), top))
    return report


class CachedEmbedder:
    """:class:`~bussola_mcp.rag.embedding.Embedder` que só responde textos do cache."""

    def __init__(self, model: str, dimension: int, table: dict[str, np.ndarray]) -> None:
        self.model = model
        self.dimension = dimension
        self._table = table

    def embed(self, texts: Sequence[str], task_type: TaskType) -> np.ndarray:
        if task_type != TASK_QUERY:
            raise EmbeddingUnavailableError("UnsupportedTask")
        try:
            return np.stack([self._table[text] for text in texts]).astype(np.float32)
        except KeyError:
            raise EmbeddingUnavailableError("NotCached") from None

    def knows(self, texts: Sequence[str]) -> bool:
        return all(text in self._table for text in texts)


def load_query_cache(path: Path = QUERY_CACHE) -> CachedEmbedder | None:
    if not path.is_file():
        return None
    with np.load(path, allow_pickle=False) as data:
        model = str(data["modelo"])
        dimension = int(data["dimensao"])
        texts = [str(t) for t in data["textos"]]
        vectors = np.asarray(data["vetores"], dtype=np.float32)
    if vectors.shape != (len(texts), dimension):
        return None
    return CachedEmbedder(model, dimension, dict(zip(texts, vectors, strict=True)))


def cache_covers(cache: CachedEmbedder | None, eval_set: EvalSet, model: str, dim: int) -> bool:
    return (
        cache is not None
        and cache.model == model
        and cache.dimension == dim
        and cache.knows(eval_set.texts)
    )


def update_query_cache(eval_set: EvalSet, model: str, dimension: int, path: Path) -> None:
    """Embute as perguntas com ``RETRIEVAL_QUERY`` (rede) e grava o cache."""
    texts = eval_set.texts
    vectors = GeminiEmbedder(model, dimension, retries=3).embed(texts, TASK_QUERY)
    with path.open("wb") as handle:
        np.savez(
            handle,
            modelo=np.array(model),
            dimensao=np.array(dimension),
            textos=np.array(texts),
            vetores=vectors.astype(np.float32),
        )


def numpy_calibration(
    index_dir: Path, embedder: CachedEmbedder, eval_set: EvalSet
) -> tuple[list[tuple[str, float | None]], list[tuple[str, float]]]:
    """Scores sem limiar: 1º acerto de cada positiva e maior score de cada negativa."""
    raw = BuscadorNumpy(index_dir, embedder=embedder, model=embedder.model, min_score=-1.0)
    total = load_manifest(index_dir).qtd_trechos
    positives: list[tuple[str, float | None]] = []
    for question in eval_set.questions:
        found = raw.buscar(question.text, total, None)
        first = next((t.score for t in found if t.trecho_id in question.expected), None)
        positives.append((question.id, first))
    negatives = []
    for negative in eval_set.negatives:
        found = raw.buscar(negative.text, 1, None)
        negatives.append((negative.id, found[0].score if found else 0.0))
    return positives, negatives


def product_rate_violations(index_dir: Path = INDEX_DIR) -> list[str]:
    """``trecho_id`` de trechos de produto com marcador de taxa (deve ficar vazio)."""
    return [
        chunk.trecho_id
        for chunk in load_chunks(index_dir)
        if chunk.tema == TemaConhecimento.PRODUTO and contem_taxa(chunk.texto)
    ]


@dataclass
class EvalRun:
    eval_set: EvalSet
    reports: list[BackendReport]
    numpy_status: str
    calibration: tuple[list[tuple[str, float | None]], list[tuple[str, float]]] | None
    rate_violations: list[str]
    min_coverage: float
    min_score: float


def run_eval(
    eval_set: EvalSet,
    *,
    index_dir: Path = INDEX_DIR,
    cache_path: Path = QUERY_CACHE,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    min_score: float = DEFAULT_MIN_SCORE,
) -> EvalRun:
    lexical = BuscadorLexico(index_dir, min_coverage=min_coverage)
    reports = [evaluate(lexical, eval_set, "lexico")]
    manifest = load_manifest(index_dir)
    calibration = None
    if not manifest.has_embeddings:
        status = "pulado: índice sem embeddings"
    else:
        assert manifest.modelo_embedding is not None and manifest.dimensao is not None
        cache = load_query_cache(cache_path)
        if not cache_covers(cache, eval_set, manifest.modelo_embedding, manifest.dimensao):
            status = "pulado: cache de perguntas ausente ou desatualizado (--atualizar-cache)"
        else:
            assert cache is not None
            vector = BuscadorNumpy(
                index_dir, embedder=cache, model=cache.model, min_score=min_score
            )
            reports.append(evaluate(vector, eval_set, "numpy"))
            calibration = numpy_calibration(index_dir, cache, eval_set)
            status = f"ok ({manifest.modelo_embedding}, dim {manifest.dimensao})"
    return EvalRun(
        eval_set=eval_set,
        reports=reports,
        numpy_status=status,
        calibration=calibration,
        rate_violations=product_rate_violations(index_dir),
        min_coverage=min_coverage,
        min_score=min_score,
    )


def _percent(value: float) -> str:
    return f"{value * 100:.0f}%"


def _score(value: float | None) -> str:
    return "—" if value is None else f"{value:.4f}"


def render_markdown(run: EvalRun) -> str:
    """Relatório em Markdown (pt-BR) para ``eval/rag/RESULTADOS.md``."""
    k = run.eval_set.k
    lines = [
        "# Resultados do eval do RAG (ciclo 002)",
        "",
        "Gerado por `make eval-rag` (`eval/rag/rodar_eval.py --resultados`). Perguntas em",
        f"[`perguntas.yaml`](perguntas.yaml); acerto = algum trecho esperado no top-{k},",
        f"sem filtro de tema. Meta: pelo menos {_percent(TARGET_HIT_RATE)} no backend `numpy`,",
        "com o `lexico` como linha de base.",
        "",
        "## Resumo",
        "",
        f"| Backend | Acertos top-{k} | Conhecimento | Produto | Negativas vazias |",
        "|---|---|---|---|---|",
    ]
    for report in run.reports:
        hits, total = report.hits()
        knowledge = report.hits("conhecimento")
        product = report.hits("produto")
        negatives = sum(n.returned == 0 for n in report.negatives)
        lines.append(
            f"| `{report.backend}` | {hits}/{total} ({_percent(report.hit_rate())}) "
            f"| {knowledge[0]}/{knowledge[1]} | {product[0]}/{product[1]} "
            f"| {negatives}/{len(report.negatives)} |"
        )
    lines += [
        "",
        f"- Backend `numpy`: {run.numpy_status}.",
        f"- Parâmetros: `lexico` com `min_coverage={run.min_coverage}` e "
        f"`single_term_coverage={DEFAULT_SINGLE_TERM_COVERAGE}`; "
        f"`numpy` com `min_score={run.min_score}`.",
        "- Trechos de produto com marcador de taxa (`%`, `a.a.`, `a.m.`, `R$`): "
        + (", ".join(run.rate_violations) if run.rate_violations else "nenhum")
        + ".",
        "",
        "## Por pergunta",
        "",
        "| Id | Tipo | Pergunta | " + " | ".join(f"`{r.backend}`" for r in run.reports) + " |",
        "|---|---|---|" + "---|" * len(run.reports),
    ]
    for index, question in enumerate(run.eval_set.questions):
        cells = []
        for report in run.reports:
            rank = report.results[index].rank
            cells.append(f"✅ {rank}º" if rank is not None else "❌")
        row = f"| {question.id} | {question.kind} | {question.text} | " + " | ".join(cells)
        lines.append(row + " |")
    lines += [
        "",
        "## Negativas (fora do domínio)",
        "",
        "| Id | Pergunta | " + " | ".join(f"`{r.backend}`" for r in run.reports) + " |",
        "|---|---|" + "---|" * len(run.reports),
    ]
    for index, negative in enumerate(run.eval_set.negatives):
        cells = []
        for report in run.reports:
            result = report.negatives[index]
            cells.append("vazio" if result.returned == 0 else f"{result.returned} trecho(s)")
        lines.append(f"| {negative.id} | {negative.text} | " + " | ".join(cells) + " |")
    if run.calibration is not None:
        positives, negatives = run.calibration
        scored = [s for _, s in positives if s is not None]
        lines += [
            "",
            "## Calibração do limiar do `numpy` (cosseno, sem limiar)",
            "",
            f"- Menor score do 1º acerto entre as positivas: {_score(min(scored))}.",
            f"- Maior score entre as negativas: {_score(max(s for _, s in negatives))}.",
            f"- Limiar adotado (`DEFAULT_MIN_SCORE`): {run.min_score}, perto do ponto médio",
            "  entre os dois grupos, para deixar folga dos dois lados.",
            "",
            "| Id | Score do 1º acerto |",
            "|---|---|",
        ]
        lines += [f"| {qid} | {_score(score)} |" for qid, score in positives]
        lines += ["", "| Negativa | Maior score |", "|---|---|"]
        lines += [f"| {qid} | {_score(score)} |" for qid, score in negatives]
    return "\n".join(lines) + "\n"


def render_summary(run: EvalRun) -> str:
    parts = []
    for report in run.reports:
        hits, total = report.hits()
        negatives = "ok" if report.negatives_ok else "FALHOU"
        parts.append(
            f"{report.backend}: {hits}/{total} ({_percent(report.hit_rate())}) no top-"
            f"{report.k}; negativas {negatives}"
        )
    if len(run.reports) == 1:
        parts.append(f"numpy {run.numpy_status}")
    return "\n".join(parts)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Avalia o RAG de conhecimento (top-k).")
    parser.add_argument("--perguntas", type=Path, default=QUESTIONS_FILE)
    parser.add_argument("--indice", type=Path, default=INDEX_DIR)
    parser.add_argument("--cache", type=Path, default=QUERY_CACHE)
    parser.add_argument("--resultados", type=Path, help="grava o relatório em Markdown")
    parser.add_argument("--atualizar-cache", action="store_true", help="embute as perguntas")
    parser.add_argument("--min-coverage", type=float, default=DEFAULT_MIN_COVERAGE)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    eval_set = load_eval_set(args.perguntas)
    if args.atualizar_cache:
        manifest = load_manifest(args.indice)
        if not manifest.has_embeddings:
            print("índice sem embeddings: nada a embutir", file=sys.stderr)
            return 1
        assert manifest.modelo_embedding is not None and manifest.dimensao is not None
        cache = load_query_cache(args.cache)
        if not cache_covers(cache, eval_set, manifest.modelo_embedding, manifest.dimensao):
            try:
                update_query_cache(
                    eval_set, manifest.modelo_embedding, manifest.dimensao, args.cache
                )
            except EmbeddingUnavailableError as error:
                print(f"falha no embedding (causa: {error.cause})", file=sys.stderr)
                return 2
    run = run_eval(
        eval_set,
        index_dir=args.indice,
        cache_path=args.cache,
        min_coverage=args.min_coverage,
        min_score=args.min_score,
    )
    print(render_summary(run))
    if args.resultados is not None:
        args.resultados.write_text(render_markdown(run), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
