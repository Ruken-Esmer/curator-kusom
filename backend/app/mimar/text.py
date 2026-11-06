"""Fixed text preprocessing."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict

PREPROCESSING_VERSION = "text-v1"

# Stop-word lists (compact, deterministic)
EN_STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have
having he her here hers herself him himself his how i if in into is it its itself just me more most
my myself no nor not now of off on once only or other our ours ourselves out over own same she should
so some such than that the their theirs them themselves then there these they this those through to
too under until up very was we were what when where which while who whom why will with you your yours
yourself yourselves also e.g eg i.e ie etc within including include includes related relevant using use
basic main major common commonly various different given relation regarding role terms term
""".split())

TR_STOPWORDS = frozenset("""
acaba ama ancak artık aslında az bazı belki biri birkaç birşey biz bu çok çünkü da daha de defa diye
eğer en gibi hem hep hepsi her hiç için ile ise kez ki kim mı mu mü nasıl ne neden nerde nerede nereye
niçin niye o sanki şey siz şu tüm ve veya ya yani olarak olan olduğu ilgili ilişkin göre arasında
""".split())

# Learning-objective "action verbs" (Bloom).  They describe the expected
# cognitive level, not the content, so they are removed for content
# similarity but kept for Bloom-level estimation.
BLOOM_VERBS: dict[str, int] = {
    # 1 remember
    "define": 1, "list": 1, "name": 1, "recall": 1, "recognize": 1, "recognise": 1, "state": 1,
    "identify": 1, "label": 1, "outline": 1, "tanımlar": 1, "sayar": 1, "listeler": 1, "tanır": 1,
    # 2 understand
    "describe": 2, "explain": 2, "summarize": 2, "summarise": 2, "classify": 2, "discuss": 2,
    "interpret": 2, "distinguish": 2, "açıklar": 2, "tanımlayabilir": 2, "betimler": 2, "sınıflandırır": 2,
    # 3 apply
    "apply": 3, "demonstrate": 3, "perform": 3, "use": 3, "calculate": 3, "examine": 3,
    "uygular": 3, "yapar": 3, "gösterir": 3,
    # 4 analyse
    "analyze": 4, "analyse": 4, "compare": 4, "differentiate": 4, "contrast": 4, "relate": 4,
    "correlate": 4, "karşılaştırır": 4, "ayırt": 4, "ilişkilendirir": 4,
    # 5 evaluate
    "evaluate": 5, "assess": 5, "justify": 5, "appraise": 5, "prioritize": 5, "prioritise": 5,
    "değerlendirir": 5,
    # 6 create / clinical management
    "plan": 6, "manage": 6, "design": 6, "formulate": 6, "develop": 6, "propose": 6,
    "planlar": 6, "yönetir": 6,
}

_TOKEN_RE = re.compile(r"[a-z0-9çğıöşüâîû]+(?:-[a-z0-9çğıöşüâîû]+)*")


def casefold_tr(text: str) -> str:
    """Turkish-safe case folding (İ→i, I→ı is ambiguous for English, so only the dotted capital is mapped…"""
    text = unicodedata.normalize("NFC", text)
    return text.replace("İ", "i").casefold()


def light_stem(token: str) -> str:
    """Very light, deterministic English suffix stripping."""
    if len(token) <= 4 or not token.isascii():
        return token
    for suf, rep in (("ies", "y"), ("sses", "ss"), ("xes", "x")):
        if token.endswith(suf):
            return token[: -len(suf)] + rep
    if token.endswith("s") and not token.endswith(("ss", "us", "is", "os")):
        return token[:-1]
    return token


@dataclass(frozen=True)
class PreprocessConfig:
    lowercase: bool = True
    remove_stopwords: bool = True
    remove_bloom_verbs: bool = True
    stem: bool = True
    min_token_len: int = 2
    version: str = PREPROCESSING_VERSION

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT_PREPROCESS = PreprocessConfig()


def raw_tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(casefold_tr(text or ""))


def tokenize(text: str, cfg: PreprocessConfig = DEFAULT_PREPROCESS) -> list[str]:
    toks = raw_tokens(text) if cfg.lowercase else _TOKEN_RE.findall(text or "")
    out: list[str] = []
    for t in toks:
        if len(t) < cfg.min_token_len:
            continue
        if cfg.remove_stopwords and (t in EN_STOPWORDS or t in TR_STOPWORDS):
            continue
        if cfg.remove_bloom_verbs and t in BLOOM_VERBS:
            continue
        out.append(light_stem(t) if cfg.stem else t)
    return out


def content_tokens_with_positions(text: str, cfg: PreprocessConfig = DEFAULT_PREPROCESS) -> list[str | None]:
    """Tokens where removed words are kept as ``None`` separators so that n-gram concept extraction does not…"""
    out: list[str | None] = []
    for t in raw_tokens(text):
        if len(t) < cfg.min_token_len or t in EN_STOPWORDS or t in TR_STOPWORDS or t in BLOOM_VERBS:
            out.append(None)
        else:
            out.append(light_stem(t) if cfg.stem else t)
    return out


def bloom_level(text: str) -> int:
    """Highest Bloom level among action verbs found in the LO (0 = unknown)."""
    levels = [BLOOM_VERBS[t] for t in raw_tokens(text) if t in BLOOM_VERBS]
    return max(levels) if levels else 0


def normalized_key(text: str) -> str:
    """Normalisation used for exact-duplicate detection in QC."""
    return " ".join(raw_tokens(text))
