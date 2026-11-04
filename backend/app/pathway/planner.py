"""CURATOR — Learning-pathway engine built on MİMAR's repetition analysis."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.mimar.analysis import AnalysisConfig, LORecord, OverlapAnalysis, split_key
from app.mimar.text import bloom_level, raw_tokens, tokenize

GEREKLI, TAZELE, TEKRAR = "gerekli", "once_tazele", "tekrar"
LABEL_TR = {GEREKLI: "Gerekli", TAZELE: "Önce tazele", TEKRAR: "Tekrar — hızlı gözden geçir"}


@dataclass
class Item:
    id: str
    block_id: str
    block_name: str
    year: int
    seq: int                 # global teaching order
    text: str
    phase: str               # "temel" (years 1–3) | "klinik" (years 4–6)
    level: int = 0           # Bloom level when the text is an objective
    sources: list[str] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)   # learning objectives of this topic, if known
    kind: str = ""                                         # lecture, lab, case discussion …


# Phases in teaching order; content met again in a later phase is studied
# at a deeper (disease / clinical) level and is not a mere repetition.
PHASE_RANK = {"temel": 0, "hastalık": 1, "klinik": 2}


def _phase(year: int) -> str:
    return "temel" if year <= 3 else "klinik"


def items_from_curriculum(curriculum: list[dict], phase_of=None) -> tuple[list[Item], dict[str, dict]]:
    phase_of = phase_of or _phase
    items, blocks, seq = [], {}, 0
    for y in sorted(curriculum, key=lambda y: y["year"]):
        for b in sorted(y["blocks"], key=lambda b: (b.get("block_number", 99), b["id"])):
            blocks[b["id"]] = {"id": b["id"], "name": b["name_tr"], "name_en": b["name_en"], "year": y["year"],
                               "weeks": b.get("weeks", ""), "prereq": list(b.get("prerequisite_ids", [])),
                               "departments": b.get("departments", []), "seq": seq,
                               "code": b.get("code", b["id"])}
            details = b.get("topic_details") or [{"title": t} for t in b.get("topics", [])]
            for i, t in enumerate(details):
                objs = t.get("objectives") or []
                level = max([bloom_level(o) for o in objs] + [bloom_level(t["title"])])
                src = f"{b['id']} · {b['name_tr']} · konu: {t['title']}"
                if t.get("first_date"):
                    src += f" · {t['first_date']}"
                if t.get("fields"):
                    src += f" · {', '.join(f.title() for f in t['fields'][:2])}"
                items.append(Item(id=t.get("id") or f"{b['id']}:{i:02d}", block_id=b["id"], block_name=b["name_tr"],
                                  year=y["year"], seq=seq, text=t["title"], phase=phase_of(y["year"]), level=level,
                                  sources=[src], objectives=list(objs), kind=t.get("kind", "")))
            seq += 1
    return items, blocks


# Words that describe the kind of activity rather than the content; a
# shared generic word alone does not make two topics related.
GENERIC = frozenset(tokenize(
    "therapy therapies management treatment principle principles basic basics clinical disease diseases system systems "
    "assessment examination care unit units history approach overview introduction general skill skills technique "
    "techniques method methods procedure procedures diagnosis diagnostic sign signs symptom symptoms disorder disorders "
    "function functions structure test tests investigation syndrome syndromes cell cells anatomy physiology pathology "
    "pharmacology biology biochemistry type types normal abnormal acute chronic common cycle medicine development "
    "emergency emergencies cancer metabolism metabolic infection infections basal injury cortex carcinoma "
    # words that recur across the real KUSOM timetables without naming content
    "formation review patient patients child children case cases discussion workshop group time research physical "
    "major elective topic topics pediatric paediatric adult evaluation imaging radiology radiological presentation "
    "aspect aspects practice session interactive skills skill daily new update approaches histology embryology "
    "dissection drug drugs pathophysiology physiopathology disease related lab laboratory principle loss nuclear "
    "application applications pattern patterns pathological continuum characteristic characteristics feature "
    "features vessel vessels nerve nerves supply age ages aging grow"))


class PathwayEngine:
    """Pre-computes repetition (same content) and relatedness links once."""

    def __init__(self, items: list[Item], blocks: dict[str, dict], rare_df: int | None = None):
        self.items, self.blocks = items, blocks
        self.aliases: dict = PLACEHOLDER_ALIASES
        self.source = "placeholder"
        self.by_id = {it.id: it for it in items}
        los = [LORecord(uid=it.id, text=it.text, activity=it.block_id, year=it.year,
                        context=" ".join(it.objectives)[:1500]) for it in items]
        cfg = AnalysisConfig(per_query_k=8, max_pairs_per_method=20000)
        cfg.concept.min_df = 2
        cfg.concept.max_df_ratio = 0.05
        self.analysis = OverlapAnalysis(los, cfg)
        self.strength: dict[frozenset, float] = {}              # shared distinctive words + agreeing methods
        self.rejected: set[frozenset] = set()                   # expert-rejected links
        self.validated: set[frozenset] = set()                  # expert-confirmed links
        self.same: dict[str, set[str]] = defaultdict(set)      # same content in another block
        self.related: dict[str, set[str]] = defaultdict(set)   # shares a concept (not the same content)
        toks = {it.id: set(tokenize(it.text)) for it in items}
        df: dict[str, int] = defaultdict(int)
        for ts in toks.values():
            for t in ts:
                df[t] += 1
        max_df = max(3, int(0.03 * len(items)))
        # one shared word links two topics only if that word is rare
        self.rare_df = rare_df if rare_df is not None else max(3, int(0.006 * len(items)))
        spec = {k: {t for t in v if t not in GENERIC} for k, v in toks.items()}
        for h in self.analysis.hybrid():
            a, b = split_key(h["pair"])
            sa, sb = spec[a], spec[b]
            if not (sa & sb):
                continue                      # nothing distinctive in common
            jac = len(sa & sb) / len(sa | sb)
            agree = len(h["method_ranks"])
            self.strength[frozenset((a, b))] = len(sa & sb) + agree + jac
            raw_jac = len(toks[a] & toks[b]) / max(1, len(toks[a] | toks[b]))
            if jac >= 0.6 and (len(sa & sb) >= 2 or raw_jac >= 0.5) or (agree >= 2 and jac >= 0.6 and raw_jac >= 0.5 and self.analysis.emb.similarity(
                    self.analysis.index[a], self.analysis.index[b]) >= 0.55):
                self.same[a].add(b); self.same[b].add(a)
            elif agree >= 2 and (len(sa & sb) >= 2 and any(df[t] <= max_df for t in sa & sb)
                                 or any(df[t] <= self.rare_df for t in sa & sb)):
                self.related[a].add(b); self.related[b].add(a)

    # expert feedback
    def set_reviews(self, rejected: set[frozenset], validated: set[frozenset]) -> None:
        self.rejected, self.validated = set(rejected), set(validated)

    def _ok(self, a: str, b: str) -> bool:
        return frozenset((a, b)) not in self.rejected

    def _mark(self, a: str, b: str) -> str:
        return " (uzman onaylı)" if frozenset((a, b)) in self.validated else ""

    def link_type(self, a: str, b: str) -> str:
        early, late = sorted((self.by_id[a], self.by_id[b]), key=lambda x: x.seq)
        if b in self.same.get(a, set()):
            deeper = self._deeper(early, late)
            return "temel" if deeper else "tekrar"
        return "ilişkili"

    def all_links(self) -> list[dict[str, Any]]:
        out = []
        for rel in (self.same, self.related):
            for a, bs in rel.items():
                for b in bs:
                    if a < b:
                        early, late = sorted((self.by_id[a], self.by_id[b]), key=lambda x: x.seq)
                        if early.seq == late.seq:
                            continue
                        out.append({"link_id": f"{early.id}>{late.id}", "type": self.link_type(a, b),
                                    "early": early, "late": late})
        return out

    # helpers
    def _rotating(self, a: Item, b: Item) -> bool:
        return (self.source == "kusom" and a.year == b.year and a.phase == "klinik" and b.phase == "klinik"
                and a.block_id != b.block_id)

    @staticmethod
    def _deeper(early: Item, late: Item) -> bool:
        if late.level and early.level and late.level > early.level:
            return True
        return PHASE_RANK.get(late.phase, 0) > PHASE_RANK.get(early.phase, 0)

    def derive_prerequisites(self, top: int = 3, min_links: int = 4) -> None:
        """Blocks without declared prerequisites get the earlier blocks they share most content with (same or related…"""
        counts: dict[str, Counter] = defaultdict(Counter)
        for rel in (self.same, self.related):
            for a, bs in rel.items():
                for b in bs:
                    ia, ib = self.by_id[a], self.by_id[b]
                    if ib.seq < ia.seq and ia.block_id != ib.block_id:
                        counts[ia.block_id][ib.block_id] += 1
        for bid, info in self.blocks.items():
            if not info["prereq"]:
                info["prereq"] = [b for b, n in counts[bid].most_common(top) if n >= min_links]
                info["prereq_derived"] = True

    def prereq_closure(self, block_id: str) -> list[str]:
        seen, stack = [], list(self.blocks[block_id]["prereq"])
        while stack:
            b = stack.pop()
            if b in self.blocks and b not in seen:
                seen.append(b)
                if not self.blocks[b].get("prereq_derived"):
                    stack.extend(self.blocks[b]["prereq"])
        return sorted(seen, key=lambda b: self.blocks[b]["seq"])

    def _earlier(self, it: Item, ids: set[str]) -> list[Item]:
        return sorted((self.by_id[x] for x in ids if self.by_id[x].seq < it.seq and self._ok(it.id, x)),
                      key=lambda x: x.seq)

    def _classify(self, it: Item) -> tuple[str, str, list[Item]]:
        """Label an item relative to everything taught before it."""
        prev_all = self._earlier(it, self.same.get(it.id, set()))
        # clerkships of one year are taken in a different order by each group:
        # a same-year clerkship is not reliably "before" this one
        rot = [p for p in prev_all if self._rotating(p, it)]
        prev_same = [p for p in prev_all if p not in rot]
        if not prev_same:
            if rot:
                r = rot[-1]
                return GEREKLI, (f"Aynı içerik {r.block_id} ({r.block_name}) stajında da var; rotasyon sıranıza göre "
                                 "o stajı önce aldıysanız burada hızlı tekrar yeterli olabilir." + self._mark(it.id, r.id)), rot
            rej = sorted((self.by_id[x] for x in self.same.get(it.id, set())
                          if self.by_id[x].seq < it.seq and not self._ok(it.id, x)), key=lambda x: x.seq)
            if rej:
                r = rej[-1]
                return GEREKLI, (f"Uzman değerlendirmesine göre {r.block_id} bloğundaki “{r.text}” ile aynı içerik değil; "
                                 "bu konu burada ilk kez ayrıntılı işleniyor."), []
            return GEREKLI, "Bu içerik müfredatta ilk kez bu blokta geliyor.", []
        p = prev_same[-1]
        if self._deeper(p, it):
            lvl = {"klinik": "klinik", "hastalık": "hastalık (patoloji, farmakoloji, klinik tablo)"}.get(it.phase, "daha ileri")
            return GEREKLI, (f"Daha önce {p.block_id} ({p.year}. sınıf) bloğunda daha temel düzeyde görüldü; "
                             f"burada {lvl} düzeyinde ele alınıyor."
                             + self._mark(it.id, p.id)), prev_same
        return TEKRAR, (f"Aynı içerik {p.block_id} ({p.block_name}, {p.year}. sınıf) bloğunda benzer düzeyde işlendi; "
                        "hızlı gözden geçirme yeterli olabilir." + self._mark(it.id, p.id)), prev_same

    def _step(self, it: Item, label: str, reason: str, refs: list[Item]) -> dict[str, Any]:
        return {"item_id": it.id, "label": label, "label_tr": LABEL_TR[label], "topic": it.text,
                "block_id": it.block_id, "block_name": it.block_name, "year": it.year, "reason": reason,
                "sources": it.sources + [r.sources[0] for r in refs[:2]]}

    def _refresh_for(self, targets: list[Item], limit: int = 12) -> list[dict[str, Any]]:
        """Earlier content the targets build on: earlier occurrences of the same content at a basic level, and…"""
        out, seen = [], set()
        tblocks = {t.block_id for t in targets}
        pre = set()
        for b in tblocks:
            pre |= set(self.prereq_closure(b))
        first_seq = min(t.seq for t in targets)
        for t in targets:
            cands = [self.by_id[x] for x in self.same.get(t.id, set()) | self.related.get(t.id, set())
                     if self._ok(t.id, x)]
            same_ids = self.same.get(t.id, set())
            for c in sorted(cands, key=lambda c: (c.id not in same_ids, c.block_id not in pre,
                                                  -self.strength.get(frozenset((t.id, c.id)), 0), -c.seq)):
                if c.seq >= first_seq or c.id in seen or self._rotating(c, t):
                    continue
                kind = "aynı içeriğin temel düzeyi" if c.id in self.same.get(t.id, set()) else "ilişkili kavram"
                seen.add(c.id)
                st = self._step(c, TAZELE, f"“{t.text}” ({t.block_id}) konusunun dayandığı {kind}; "
                                           f"{c.block_id} ({c.year}. sınıf) bloğundan." + self._mark(t.id, c.id), [t])
                st["_rank"] = (kind != "aynı içeriğin temel düzeyi", c.block_id not in pre,
                               -self.strength.get(frozenset((t.id, c.id)), 0))
                out.append(st)
        out.sort(key=lambda s: (s["_rank"]))
        out = out[:limit]
        out.sort(key=lambda s: (s["block_id"] not in pre, self.blocks[s["block_id"]]["seq"]))
        for s in out:
            s.pop("_rank", None)
        return out

    # the three goals
    def plan_block(self, block_id: str) -> dict[str, Any]:
        b = self.blocks[block_id]
        targets = [it for it in self.items if it.block_id == block_id]
        steps = [s for s in self._refresh_for(targets)]
        for it in targets:
            lab, why, refs = self._classify(it)
            steps.append(self._step(it, lab, why, refs))
        prereq = self.prereq_closure(block_id)
        return self._finish("blok", f"{b['name']} ({block_id}) hazırlığı", steps,
                            {"block": block_id, "prerequisites": prereq})

    def plan_exam(self, block_ids: list[str]) -> dict[str, Any]:
        block_ids = sorted(block_ids, key=lambda x: self.blocks[x]["seq"])
        targets = [it for it in self.items if it.block_id in block_ids]
        steps = self._refresh_for(targets, limit=8)
        studied: dict[str, Item] = {}
        for it in sorted(targets, key=lambda x: x.seq):
            dup = next((studied[s] for s in self.same.get(it.id, set()) if s in studied and self._ok(it.id, s)), None)
            if dup:
                steps.append(self._step(it, TEKRAR, f"Bu sınav kapsamında {dup.block_id} bloğunda zaten çalışılan "
                                                    f"“{dup.text}” ile aynı içerik; bir kez çalışmak yeterli.", [dup]))
            else:
                lab, why, refs = self._classify(it)
                if lab == TEKRAR:   # repeated from before the exam scope → still exam material, review quickly
                    why = why + " Sınav kapsamında olduğu için hızlı tekrar önerilir."
                steps.append(self._step(it, lab, why, refs))
            studied[it.id] = it
        names = ", ".join(block_ids)
        return self._finish("sınav", f"Sınav hazırlığı ({names})", steps, {"blocks": block_ids})

    def plan_year(self, year: int) -> dict[str, Any]:
        block_ids = [b for b, v in sorted(self.blocks.items(), key=lambda kv: kv[1]["seq"]) if v["year"] == year]
        steps = []
        for bid in block_ids:
            targets = [it for it in self.items if it.block_id == bid]
            steps += self._refresh_for(targets, limit=3)
            for it in targets:
                lab, why, refs = self._classify(it)
                steps.append(self._step(it, lab, why, refs))
        return self._finish("yıl", f"{year}. sınıf yıl planı", steps, {"year": year, "blocks": block_ids})

    def _finish(self, kind: str, title: str, steps: list[dict], target: dict) -> dict[str, Any]:
        seen, uniq = set(), []
        for s in steps:
            key = (s["item_id"], s["label"])
            if key not in seen:
                seen.add(key); uniq.append(s)
        for i, s in enumerate(uniq, start=1):
            s["order"] = i
        counts = {k: sum(1 for s in uniq if s["label"] == k) for k in (GEREKLI, TAZELE, TEKRAR)}
        return {"kind": kind, "title": title, "target": target, "steps": uniq, "counts": counts}


#  Request understanding (Turkish / English)

_PATH_WORDS = re.compile(r"(öğrenme yol|yol öner|pathway|study plan|çalışma plan|hazırlan|prepare|neleri çalış|"
                         r"ne çalış|neyi çalış|sınav|exam|yıl plan|dönem plan|planı)", re.I)
_SHOW = re.compile(r"\b(YOL-\d{4})\b", re.I)
PLACEHOLDER_ALIASES = {"kardiyoloji": "Y5R1", "nöroloji": "Y5R1", "radyoloji": "Y5R2", "enfeksiyon": "Y5R2",
           "dahiliye": "Y4R1", "iç hastalıkları": "Y4R1", "cerrahi": "Y4R2", "pediatri": "Y4R3", "çocuk": "Y4R3",
           "kadın doğum": "Y4R4", "kadın hastalıkları": "Y4R4", "psikiyatri": "Y4R5", "acil": "Y4R5",
           "intörnlük": "Y6I1", "kardiyovasküler": "Y2B1", "solunum": "Y2B2", "hematoloji": "Y2B3",
           "renal": "Y2B4", "böbrek": "Y2B4", "sinir sistemi": "Y3B1", "gastrointestinal": "Y3B2",
           "endokrin": "Y3B3", "kas-iskelet": "Y3B4", "kas iskelet": "Y3B4", "anatomi": "Y1B3",
           "biyokimya": "Y1B4", "hücre": "Y1B2", "tıbba giriş": "Y1B1"}


def is_pathway_request(text: str) -> bool:
    return bool(_PATH_WORDS.search(text))


ALIASES = PLACEHOLDER_ALIASES        # kept for callers that import it


def _code_ids(text: str, blocks: dict[str, dict]) -> list[str]:
    """Block ids written by the student: placeholder ids (Y3B1) or real codes (CARD 314, card314)."""
    up = text.upper().replace("İ", "I")
    out = [b for b in re.findall(r"\b([YR]\d[A-Z]{1,2}\d)\b", up) if b in blocks]
    for pre, num in re.findall(r"\b([A-Z]{4})\s*-?\s*(\d{3})\b", up):
        if pre + num in blocks and pre + num not in out:
            out.append(pre + num)
    return out


def parse_request(text: str, blocks: dict[str, dict], aliases: dict | None = None) -> dict[str, Any]:
    low = text.replace("İ", "i").replace("I", "ı").lower().replace("i̇", "i")
    aliases = PLACEHOLDER_ALIASES if aliases is None else aliases
    found = _code_ids(text, blocks)
    ym = re.search(r"(\d)\s*\.?\s*(sınıf|yıl|year)", low)
    year = int(ym.group(1)) if ym else None
    for k, v in sorted(aliases.items(), key=lambda kv: -len(kv[0])):
        if not re.search(rf"(?<![a-zçğıöşü]){re.escape(k)}", low):
            continue
        cands = [x for x in ([v] if isinstance(v, str) else v) if x in blocks]
        if year:   # "3. sınıf kardiyoloji" → the year-3 block
            cands = [x for x in cands if blocks[x]["year"] == year] or cands
        if cands and cands[0] not in found:
            found.append(cands[0])
    if re.search(r"(sınav|exam)", low):
        scope = found or ([b for b, v in blocks.items() if v["year"] == year] if year else [])
        return {"kind": "sınav", "blocks": scope, "year": year}
    if re.search(r"(yıl plan|dönem plan|yıllık|bu yıl|bu dönem|year plan)", low) or (year and not found):
        return {"kind": "yıl", "year": year}
    if found:
        return {"kind": "blok", "block": found[0], "student_year": year}
    return {"kind": "belirsiz"}


@lru_cache(maxsize=1)
def default_engine() -> PathwayEngine:
    from app.data.curriculum.source import active_aliases, active_curriculum, active_phase_of, active_source
    items, blocks = items_from_curriculum(active_curriculum(), active_phase_of())
    e = PathwayEngine(items, blocks)
    e.aliases = active_aliases()
    e.source = active_source()
    if e.source == "kusom":
        e.derive_prerequisites()
    return e


def build(parsed: dict[str, Any], engine: PathwayEngine | None = None) -> dict[str, Any] | None:
    e = engine or default_engine()
    if parsed["kind"] == "blok":
        return e.plan_block(parsed["block"])
    if parsed["kind"] == "sınav" and parsed.get("blocks"):
        return e.plan_exam(parsed["blocks"])
    if parsed["kind"] == "yıl" and parsed.get("year") in {v["year"] for v in e.blocks.values()}:
        return e.plan_year(parsed["year"])
    return None
