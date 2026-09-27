"""``BuscadorLexico``: BM25 sobre o índice do RAG, sem GCP (backend ``lexico``).

- Normalização pt-BR de :mod:`bussola_mcp.rag.text` nos trechos e na pergunta.
- O título da seção pesa ``title_weight`` vezes o corpo (BM25F simplificado).
- **Cobertura mínima:** um trecho só entra se os termos da pergunta que ele
  contém somarem pelo menos ``min_coverage`` do IDF total da pergunta, ou
  ``single_term_coverage`` quando ele casa um único termo. Um termo que não
  existe no corpus vale o IDF máximo. Assim, "previsão do tempo" não devolve
  nada só porque "tempo" aparece em algum trecho.
- Ordem: score (BM25, 4 casas) decrescente, empate por ``trecho_id``, só
  ``score > 0`` (contratos §4).
"""

import math
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from bussola_mcp.contratos import TemaConhecimento, Trecho, TrechoCorpus
from bussola_mcp.rag.index import INDEX_DIR, load_chunks, load_manifest
from bussola_mcp.rag.text import tokenize

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75
DEFAULT_TITLE_WEIGHT = 2.0
DEFAULT_MIN_COVERAGE = 0.2  # calibrado em eval/rag/RESULTADOS.md
DEFAULT_SINGLE_TERM_COVERAGE = 0.5


def _unique(terms: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(terms))


class BuscadorLexico:
    """:class:`~bussola_mcp.dominio.interfaces.BuscadorContexto` por BM25.

    Carrega o índice uma vez, no construtor. ``chunks`` permite montar o
    buscador direto de uma lista (testes), sem ler o índice.
    """

    def __init__(
        self,
        index_dir: Path = INDEX_DIR,
        *,
        chunks: Sequence[TrechoCorpus] | None = None,
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
        title_weight: float = DEFAULT_TITLE_WEIGHT,
        min_coverage: float = DEFAULT_MIN_COVERAGE,
        single_term_coverage: float = DEFAULT_SINGLE_TERM_COVERAGE,
    ) -> None:
        if chunks is None:
            chunks = load_chunks(index_dir, load_manifest(index_dir))
        self._chunks = list(chunks)
        self._k1 = k1
        self._b = b
        self.min_coverage = min_coverage
        self.single_term_coverage = single_term_coverage

        self._tf: list[dict[str, float]] = []
        self._length: list[float] = []
        document_frequency: Counter[str] = Counter()
        for chunk in self._chunks:
            weights: Counter[str] = Counter()
            for term in tokenize(chunk.texto):
                weights[term] += 1.0
            for term in tokenize(chunk.titulo):
                weights[term] += title_weight
            self._tf.append(dict(weights))
            self._length.append(sum(weights.values()))
            document_frequency.update(weights.keys())
        self._df = dict(document_frequency)
        self._n = len(self._chunks)
        self._avg_length = (sum(self._length) / self._n) if self._n else 0.0

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log(1.0 + (self._n - df + 0.5) / (df + 0.5))

    def _bm25(self, index: int, terms: Sequence[str], idf: dict[str, float]) -> float:
        tf = self._tf[index]
        norm = self._k1 * (1.0 - self._b + self._b * self._length[index] / self._avg_length)
        return sum(
            idf[term] * tf[term] * (self._k1 + 1.0) / (tf[term] + norm)
            for term in terms
            if term in tf
        )

    def _covers(self, matched: Sequence[str], idf: dict[str, float], total_idf: float) -> bool:
        coverage = sum(idf[term] for term in matched) / total_idf
        if len(matched) == 1:
            return coverage >= self.single_term_coverage
        return coverage >= self.min_coverage

    def buscar(self, pergunta: str, k: int, tema: TemaConhecimento | None = None) -> list[Trecho]:
        """Até ``k`` trechos relevantes para ``pergunta``, filtrados por ``tema``."""
        if k <= 0 or not self._chunks:
            return []
        terms = _unique(tokenize(pergunta or ""))
        if not terms:
            return []
        topic = TemaConhecimento(tema) if tema is not None else None
        idf = {term: self._idf(term) for term in terms}
        total_idf = sum(idf.values())

        ranked: list[tuple[float, TrechoCorpus]] = []
        for index, chunk in enumerate(self._chunks):
            if topic is not None and chunk.tema != topic:
                continue
            matched = [term for term in terms if term in self._tf[index]]
            if not matched or not self._covers(matched, idf, total_idf):
                continue
            score = round(self._bm25(index, matched, idf), 4)
            if score > 0:
                ranked.append((score, chunk))
        ranked.sort(key=lambda item: (-item[0], item[1].trecho_id))
        return [
            Trecho.model_validate({**chunk.model_dump(), "score": score})
            for score, chunk in ranked[:k]
        ]
