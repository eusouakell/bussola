"""Normalização de texto em pt-BR para a busca léxica.

Tudo é determinístico e sem dependência externa:

1. remove acentos (NFKD) e caixa;
2. separa em palavras alfanuméricas;
3. descarta stopwords e termos de uma letra;
4. reduz cada termo a um radical leve (plural + sufixos comuns), para que
   "parcelar", "parcela" e "parcelamento" caiam no mesmo termo. Uma vogal
   final só sai depois de consoante, então "cartão" não vira "carta".

O radical é propositalmente simples (uma versão curta do RSLP): basta para
aproximar variações da mesma palavra no corpus e nas perguntas.
"""

import re
import unicodedata

_WORD = re.compile(r"[a-z0-9]+")

STOPWORDS: frozenset[str] = frozenset(
    """
    a ao aos aquela aquelas aquele aqueles aquilo as ate cada com como da das de dela
    delas dele deles depois do dos e ela elas ele eles em entre era essa essas esse
    esses esta estao estas este estes eu foi for ha isso isto ja la lhe lhes mais mas
    me mesma mesmo meu meus minha minhas muita muitas muito muitos na nas nem no nos
    nossa nossas nosso nossos num numa o os ou para pela pelas pelo pelos pode posso
    pra pro qual quais quando quanto quanta quantas quantos que quem se sem ser seu
    seus so sua suas tambem te tem ter teu tua um uma umas uns voce voces vou sao
    devo deve preciso consigo quero queria gostaria saber sobre onde tudo todo toda
    todos todas algum alguma alguns algumas coisa fazer faco faz isso nao sim ai
    nele nela neles nelas por dois duas tenho tenha tinha estou vai
    """.split()
)

# Plural: aplicado antes dos sufixos (ordem importa: o mais longo primeiro).
_PLURALS: tuple[tuple[str, str], ...] = (
    ("coes", "cao"),
    ("oes", "ao"),
    ("aes", "ao"),
    ("ais", "al"),
    ("eis", "el"),
    ("ns", "m"),
    ("res", "r"),
    ("zes", "z"),
    ("ses", "s"),
)

# Sufixos derivacionais e flexionais removidos uma vez, do mais longo ao mais curto.
_SUFFIXES: tuple[str, ...] = (
    "amento",
    "imento",
    "mente",
    "idade",
    "acao",
    "icao",
    "ucao",
    "ador",
    "edor",
    "idor",
    "ando",
    "endo",
    "indo",
    "ada",
    "ida",
    "ado",
    "ido",
    "ar",
    "er",
    "ir",
    "a",
    "e",
    "o",
)

_MIN_STEM = 3
_VOWELS = frozenset("aeiou")


def fold(text: str) -> str:
    """Remove acentos e caixa, preservando só caracteres ASCII."""
    decomposed = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in decomposed if not unicodedata.combining(c))
    return folded.casefold().encode("ascii", "ignore").decode("ascii")


def stem(term: str) -> str:
    """Radical leve de um termo já sem acento e em minúsculas."""
    if len(term) <= _MIN_STEM or term.isdigit():
        return term
    for suffix, replacement in _PLURALS:
        if term.endswith(suffix) and len(term) - len(suffix) >= 2:
            term = term[: -len(suffix)] + replacement
            break
    else:
        if term.endswith("s") and not term.endswith(("ss", "us", "is")):
            term = term[:-1]
    for suffix in _SUFFIXES:
        if term.endswith(suffix) and len(term) - len(suffix) >= _MIN_STEM:
            if len(suffix) == 1 and term[-2] in _VOWELS:
                # "cartao" fica "cartao" (não "carta"); "meio" fica "meio"
                return term
            return term[: -len(suffix)]
    return term


def tokenize(text: str) -> list[str]:
    """Termos de busca de um texto: sem acento, sem stopword, reduzidos ao radical."""
    terms: list[str] = []
    for word in _WORD.findall(fold(text)):
        if len(word) < 2 or word in STOPWORDS:
            continue
        terms.append(stem(word))
    return terms
