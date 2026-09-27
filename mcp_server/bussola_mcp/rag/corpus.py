"""Corpus de conhecimento em Markdown: leitura e validação (contratos §4).

Formato de ``data/rag/corpus/<tema>/<doc_id>.md``::

    ---
    titulo: Portabilidade de crédito
    tema: norma_bacen
    fonte_nome: Conselho Monetário Nacional
    fonte_referencia: Resolução CMN nº 4.292/2013
    fonte_url: https://...          (opcional; obrigatório no tema produto)
    ---

    ## Título da seção 1
    Texto da seção 1.

    ## Título da seção 2
    ...

Cada seção ``##`` vira um :class:`TrechoCorpus` com ``trecho_id = "<doc_id>#<n>"``
(n a partir de 1). O título do trecho é o da seção. A fonte vem do cabeçalho.

Este módulo é usado só na construção do índice (``data/rag/``) e nos testes; o
buscador em tempo de execução lê apenas o índice.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from bussola_mcp.contratos import (
    MARCADORES_TAXA,
    FonteTrecho,
    ProdutoCatalogo,
    TemaConhecimento,
    TrechoCorpus,
)

REQUIRED_FIELDS: tuple[str, ...] = ("titulo", "tema", "fonte_nome", "fonte_referencia")
OPTIONAL_FIELDS: tuple[str, ...] = ("fonte_url",)
KNOWN_TOPICS: frozenset[str] = frozenset(t.value for t in TemaConhecimento)

DOC_ID_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
_HEADING_RE = re.compile(r"^##\s+(.*?)\s*#*\s*$")
_FIELD_RE = re.compile(r"^([a-z_]+)\s*:\s*(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+")

# Dados que identificam pessoas ou contas nunca entram no corpus (conhecimento geral).
SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "UUID",
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE
        ),
    ),
    ("CPF", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("CNPJ", re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")),
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("número de cartão", re.compile(r"\b(?:\d{4}[ .-]){3}\d{4}\b")),
    ("número longo (conta ou documento)", re.compile(r"\b\d{11,}\b")),
)


class CorpusFormatError(ValueError):
    """Arquivo do corpus fora do formato (cabeçalho ausente ou malformado)."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


@dataclass(frozen=True)
class Section:
    title: str
    text: str


@dataclass(frozen=True)
class Document:
    path: Path
    doc_id: str
    header: dict[str, str]
    sections: tuple[Section, ...]
    preamble: str

    @property
    def topic(self) -> str:
        return self.header.get("tema", "")

    def source(self) -> FonteTrecho:
        return FonteTrecho(
            nome=self.header["fonte_nome"],
            referencia=self.header["fonte_referencia"],
            url=self.header.get("fonte_url") or None,
        )


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value


def _parse_header(path: Path, lines: list[str]) -> tuple[dict[str, str], int]:
    if not lines or lines[0].strip() != "---":
        raise CorpusFormatError(path, "sem cabeçalho (o arquivo deve começar com ---)")
    header: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return header, index + 1
        if not line.strip():
            continue
        match = _FIELD_RE.match(line.strip())
        if match is None:
            raise CorpusFormatError(path, f"linha {index + 1} do cabeçalho fora de 'campo: valor'")
        key, value = match.group(1), _strip_quotes(match.group(2))
        if key in header:
            raise CorpusFormatError(path, f"campo repetido no cabeçalho: {key}")
        header[key] = value
    raise CorpusFormatError(path, "cabeçalho sem o --- de fechamento")


def _join_block(block: list[str]) -> str:
    if any(_LIST_ITEM_RE.match(line) for line in block):
        return "\n".join(line.strip() for line in block)
    return " ".join(line.strip() for line in block)


def _normalize_body(lines: Iterable[str]) -> str:
    """Junta linhas quebradas do mesmo parágrafo; parágrafos ficam separados por linha em branco."""
    paragraphs: list[str] = []
    block: list[str] = []
    for line in lines:
        if line.strip():
            block.append(line)
        elif block:
            paragraphs.append(_join_block(block))
            block = []
    if block:
        paragraphs.append(_join_block(block))
    return "\n\n".join(paragraphs)


def parse_document(path: Path) -> Document:
    """Lê um arquivo do corpus. Levanta :class:`CorpusFormatError` se o cabeçalho for inválido."""
    lines = path.read_text(encoding="utf-8").splitlines()
    header, body_start = _parse_header(path, lines)
    preamble: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    for line in lines[body_start:]:
        match = _HEADING_RE.match(line)
        if match is not None:
            sections.append((match.group(1).strip(), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            preamble.append(line)
    return Document(
        path=path,
        doc_id=path.stem,
        header=header,
        sections=tuple(Section(title, _normalize_body(body)) for title, body in sections),
        preamble=_normalize_body(preamble),
    )


def document_chunks(document: Document) -> list[TrechoCorpus]:
    """Um :class:`TrechoCorpus` por seção ``##``, na ordem do arquivo."""
    source = document.source()
    return [
        TrechoCorpus(
            doc_id=document.doc_id,
            trecho_id=f"{document.doc_id}#{number}",
            titulo=section.title,
            tema=TemaConhecimento(document.topic),
            texto=section.text,
            fonte=source,
        )
        for number, section in enumerate(document.sections, start=1)
    ]


def document_paths(corpus_dir: Path) -> list[Path]:
    """Todos os ``.md`` do corpus, em ordem estável (tema, doc_id)."""
    return sorted(corpus_dir.rglob("*.md"), key=lambda p: p.relative_to(corpus_dir).as_posix())


def load_corpus(corpus_dir: Path) -> list[TrechoCorpus]:
    """Trechos de todo o corpus, na ordem tema → doc_id → seção.

    Não valida: rode :func:`validate_corpus` antes (o ``indexar.py`` faz isso).
    """
    chunks: list[TrechoCorpus] = []
    for path in document_paths(corpus_dir):
        chunks.extend(document_chunks(parse_document(path)))
    return chunks


def _sensitive_hits(text: str) -> list[str]:
    return [label for label, pattern in SENSITIVE_PATTERNS if pattern.search(text)]


def _rate_markers(text: str) -> list[str]:
    return [marker for marker in MARCADORES_TAXA if marker in text]


def _validate_document(document: Document, catalog: dict[str, ProdutoCatalogo] | None) -> list[str]:
    problems: list[str] = []
    header = document.header
    folder = document.path.parent.name

    for field in REQUIRED_FIELDS:
        if not header.get(field, "").strip():
            problems.append(f"campo obrigatório ausente: {field}")
    for field in header:
        if field not in REQUIRED_FIELDS and field not in OPTIONAL_FIELDS:
            problems.append(f"campo desconhecido no cabeçalho: {field}")

    topic = header.get("tema", "").strip()
    if topic and topic not in KNOWN_TOPICS:
        problems.append(f"tema inválido: {topic}")
    elif topic and topic != folder:
        problems.append(f"tema do cabeçalho ({topic}) difere da pasta ({folder})")

    if not DOC_ID_RE.match(document.doc_id):
        problems.append("doc_id inválido: use minúsculas, dígitos, '-' ou '_'")

    url = header.get("fonte_url", "").strip()
    if url and not url.startswith("https://"):
        problems.append("fonte_url deve começar com https://")

    if document.preamble:
        problems.append("texto antes da primeira seção ##")
    if not document.sections:
        problems.append("nenhuma seção ##")
    for number, section in enumerate(document.sections, start=1):
        if not section.title:
            problems.append(f"seção {number} sem título")
        if not section.text:
            problems.append(f"seção {number} vazia")

    full_text = document.path.read_text(encoding="utf-8")
    for label in _sensitive_hits(full_text):
        problems.append(f"contém dado de cliente ou identificador ({label})")

    if topic == TemaConhecimento.PRODUTO.value:
        if not url:
            problems.append("tema produto exige fonte_url (página oficial)")
        text_without_url = full_text.replace(url, "") if url else full_text
        for marker in _rate_markers(text_without_url):
            problems.append(f"tema produto não pode ter taxa ou valor ({marker!r})")
        if catalog is not None:
            product = catalog.get(document.doc_id)
            if product is None:
                problems.append("produto fora de contracts/catalogo_produtos.json")
            elif url and url != product.fonte_oficial:
                problems.append("fonte_url difere da fonte oficial do catálogo")
    return problems


def validate_corpus(
    corpus_dir: Path, catalog: Sequence[ProdutoCatalogo] | None = None
) -> list[str]:
    """Problemas do corpus, um por linha, no formato ``<arquivo>: <problema>``.

    Lista vazia = corpus válido. Com ``catalog``, exige também um documento
    ``produto`` por ``produto_id``, com ``fonte_url`` igual à fonte oficial.
    """
    problems: list[str] = []
    by_id = {p.produto_id: p for p in catalog} if catalog is not None else None
    seen: dict[str, str] = {}
    paths = document_paths(corpus_dir)
    if not paths:
        return [f"{corpus_dir}: corpus vazio"]

    for path in paths:
        relative = path.relative_to(corpus_dir).as_posix()
        if len(path.relative_to(corpus_dir).parts) != 2:
            problems.append(f"{relative}: fora de <tema>/<doc_id>.md")
            continue
        if path.parent.name not in KNOWN_TOPICS:
            problems.append(f"{relative}: pasta de tema inválida ({path.parent.name})")
        try:
            document = parse_document(path)
        except CorpusFormatError as error:
            problems.append(f"{relative}: {error.message}")
            continue
        if document.doc_id in seen:
            problems.append(f"{relative}: doc_id duplicado (também em {seen[document.doc_id]})")
        else:
            seen[document.doc_id] = relative
        problems.extend(f"{relative}: {p}" for p in _validate_document(document, by_id))

    if by_id is not None:
        for product_id in sorted(by_id):
            if seen.get(product_id) != f"produto/{product_id}.md":
                problems.append(f"produto/{product_id}.md: produto do catálogo sem documento")
    return problems
