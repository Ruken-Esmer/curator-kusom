"""CURATOR — expert review of the learning-pathway engine during development."""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Any

from app.mimar.metrics import agreement, binomial_ci
from app.mimar.store import Store, now_iso
from app.pathway.planner import LABEL_TR, build, default_engine, parse_request

CLAIM = {
    "tekrar": "“{late}” ({lb}, {ly}. sınıf), “{early}” ({eb}, {ey}. sınıf) ile aynı içeriği aynı düzeyde tekrarlıyor; öğrenciye “hızlı gözden geçir” denecek.",
    "temel": "“{early}” ({eb}, {ey}. sınıf), “{late}” ({lb}, {ly}. sınıf) konusunun temel düzeyidir; öğrenciye önce tazelemesi önerilecek.",
    "ilişkili": "“{early}” ({eb}, {ey}. sınıf), “{late}” ({lb}, {ly}. sınıf) konusunu öğrenmeden önce tazelenmesi gereken ilişkili bilgidir.",
}
LINK_DECISIONS = ("uygun", "uygun_degil", "emin_degilim")
WRONG_KIND = {"ilgisiz": "İki konu ilişkili değil", "aslinda_yeni": "Tekrar değil; sonraki konu yeni ve gerekli",
              "aslinda_temel": "Tekrar değil; temel → ileri düzey ilişkisi", "aslinda_tekrar": "Aslında aynı düzeyde tekrar"}
PATH_DECISIONS = ("uygun", "kucuk_duzeltme", "uygun_degil")

DEFAULT_THRESHOLDS = {"link_ok_min": 0.80, "link_ci_lower_min": 0.70, "critical_max": 0.05,
                      "path_ok_min": 0.80, "ac1_min": 0.60, "min_reviewers": 2,
                      "min_links_per_type": 30, "min_paths": 6, "min_common_for_agreement": 10}

PLACEHOLDER_GOALS = ["Kardiyoloji stajına hazırlanmak istiyorum", "Pediatri stajına hazırlanmak istiyorum",
                "İç hastalıkları stajına hazırlanmak istiyorum", "Sinir sistemi bloğuna hazırlanmak istiyorum",
                "Y3B3 ve Y3B4 sınavına hazırlanmak istiyorum", "Y2B1 ve Y2B2 sınavına hazırlanmak istiyorum",
                "3. sınıf yıl planı", "4. sınıf yıl planı"]
SAMPLE_GOALS = PLACEHOLDER_GOALS
# Goals on the real KUSOM 2025–2026 programme: every year, every goal type.
KUSOM_GOALS = ["CARD 314 bloğuna hazırlanmak istiyorum", "NRVS 207 bloğuna hazırlanmak istiyorum",
               "Pediatri stajına hazırlanmak istiyorum", "İç hastalıkları stajına hazırlanmak istiyorum",
               "Nöroloji stajına hazırlanmak istiyorum", "RESP 313 ve CARD 314 sınavına hazırlanmak istiyorum",
               "CIRC 204 ve NUTI 205 sınavına hazırlanmak istiyorum", "3. sınıf yıl planı", "4. sınıf yıl planı"]


def sample_goals(engine) -> list[str]:
    return KUSOM_GOALS if getattr(engine, "source", "") == "kusom" else PLACEHOLDER_GOALS


# Why a link is in the expert queue.  Only "rastgele" and "tam" links enter
# the accuracy estimate; the others are checked one by one but would bias it.
ORIGINS = {"tam": "tümü inceleniyor", "rastgele": "rastgele örnek", "örnek yol": "örnek yolda geçiyor",
           "geri bildirim": "kullanıcı bildirdi"}
ESTIMATE_ORIGINS = ("tam", "rastgele")
CENSUS_TYPES = ("tekrar",)   # few and the riskiest ("skim this"): every one is reviewed


def _link_doc(l: dict[str, Any], origin: str) -> dict[str, Any]:
    ea, la, t = l["early"], l["late"], l["type"]
    return {"id": l["link_id"], "type": t, "origin": origin, "early_id": ea.id, "late_id": la.id,
            "claim": CLAIM[t].format(early=ea.text, eb=ea.block_id, ey=ea.year, late=la.text, lb=la.block_id, ly=la.year),
            "early": {"topic": ea.text, "block": f"{ea.block_id} · {ea.block_name}", "year": ea.year,
                      "objectives": ea.objectives[:4]},
            "late": {"topic": la.text, "block": f"{la.block_id} · {la.block_name}", "year": la.year,
                     "objectives": la.objectives[:4]}}


class ExpertReview:
    def __init__(self, store: Store):
        self.store = store
        # reviews are kept per curriculum source, so switching from the
        # demonstration curriculum to the real KUSOM data starts a clean sample
        self.ns = "pwk" if getattr(default_engine(), "source", "") == "kusom" else "pw"

    # samples
    def ensure_sample(self, per_type: int = 30, seed: int = 20261104) -> dict[str, Any]:
        cur = self.store.get(self.ns + "_meta", "sample")
        if cur and cur.get("version", 1) >= 2:
            return cur
        e = default_engine()
        rng = random.Random(seed)
        have = {l["id"] for l in self.store.list(self.ns + "_link")} if cur else set()
        by_type: dict[str, list] = defaultdict(list)
        for l in e.all_links():
            by_type[l["type"]].append(l)
        new = []
        for t in ("tekrar", "temel", "ilişkili"):
            pool = sorted(by_type[t], key=lambda l: l["link_id"])
            if t in CENSUS_TYPES:
                chosen, origin = pool, "tam"
            else:
                chosen, origin = (pool if len(pool) <= per_type else rng.sample(pool, per_type)), "rastgele"
            new += [_link_doc(l, origin) for l in chosen if l["link_id"] not in have]
        rng.shuffle(new)
        have |= {d["id"] for d in new}
        # sample pathways, and every link their suggestions rest on
        paths = None if cur else []
        if not cur:
            for i, g in enumerate(sample_goals(e), start=1):
                parsed = parse_request(g, e.blocks, e.aliases)
                if build(parsed, e):
                    paths.append({"id": f"P{i:02d}", "goal": g, "parsed": parsed})
        for p in (paths if paths is not None else self.store.list(self.ns + "_path")):
            for st in (build(p["parsed"], e) or {"steps": []})["steps"]:
                lk = st.get("link")
                if lk and lk["link_id"] not in have:
                    new.append(_link_doc(e.link_record(lk["early_id"], lk["late_id"]), "örnek yol"))
                    have.add(lk["link_id"])
        self.store.put_many(self.ns + "_link", new)
        if paths:
            self.store.put_many(self.ns + "_path", paths)
        counts = Counter(l["origin"] for l in self.store.list(self.ns + "_link"))
        meta = {"created": now_iso(), "seed": seed, "version": 2, "source": e.source,
                "links": dict(Counter(l["type"] for l in self.store.list(self.ns + "_link")
                                      if l.get("origin", "rastgele") in ESTIMATE_ORIGINS)),
                "origins": dict(counts), "paths": self.store.count(self.ns + "_path"),
                "thresholds": (cur or {}).get("thresholds", DEFAULT_THRESHOLDS)}
        meta = self.store.put(self.ns + "_meta", meta, id="sample")
        self.store.audit("system", "pathway.expert_sample", "sample", meta["origins"])
        return meta

    # user feedback from the student screen
    def report(self, early_id: str, late_id: str, note: str = "", reporter: str = "öğrenci") -> dict[str, Any]:
        e = default_engine()
        if early_id not in e.by_id or late_id not in e.by_id:
            raise KeyError("bilinmeyen konu")
        self.ensure_sample()
        rec = e.link_record(early_id, late_id)
        doc = self.store.get(self.ns + "_link", rec["link_id"])
        if not doc:
            doc = self.store.put(self.ns + "_link", _link_doc(rec, "geri bildirim"), id=rec["link_id"])
        fb = self.store.put(self.ns + "_feedback", {"link": rec["link_id"], "note": note[:500], "by": reporter,
                                                    "at": now_iso()})
        n = len([f for f in self.store.list(self.ns + "_feedback") if f["link"] == rec["link_id"]])
        self.store.update(self.ns + "_link", rec["link_id"], {"reports": n})
        self.store.audit(reporter, "pathway.feedback", rec["link_id"], {"note": note[:120]})
        return {"link_id": rec["link_id"], "in_queue": True, "reports": n, "origin": doc.get("origin")}

    def thresholds(self) -> dict[str, float]:
        m = self.store.get(self.ns + "_meta", "sample")
        return (m or {}).get("thresholds", DEFAULT_THRESHOLDS)

    def set_thresholds(self, user: str, th: dict[str, float]) -> dict[str, float]:
        m = self.ensure_sample()
        new = {**m["thresholds"], **{k: float(v) for k, v in th.items() if k in DEFAULT_THRESHOLDS}}
        self.store.update(self.ns + "_meta", "sample", {"thresholds": new})
        self.store.audit(user, "pathway.thresholds", "sample", new)
        return new

    # reviewing
    def link_queue(self, user: str) -> list[dict[str, Any]]:
        self.ensure_sample()
        mine = {r["item"]: r for r in self.store.list(self.ns + "_link_review", parent=user)}
        notes: dict[str, list[str]] = defaultdict(list)
        for f in self.store.list(self.ns + "_feedback"):
            if f.get("note"):
                notes[f["link"]].append(f["note"])
        rows = [{**l, "origin": l.get("origin", "rastgele"), "origin_tr": ORIGINS.get(l.get("origin", "rastgele"), ""),
                 "report_notes": list(dict.fromkeys(notes.get(l["id"], [])))[-3:], "mine": mine.get(l["id"])}
                for l in self.store.list(self.ns + "_link")]
        rows.sort(key=lambda r: -(r.get("reports") or 0))     # links students reported come first
        return rows

    def review_link(self, user: str, link_id: str, decision: str, wrong_kind: str = "", note: str = "") -> dict:
        if decision not in LINK_DECISIONS:
            raise ValueError("geçersiz karar")
        if decision == "uygun_degil" and wrong_kind not in WRONG_KIND:
            raise ValueError("uygun değilse doğrusunu seçin")
        if not self.store.get(self.ns + "_link", link_id):
            raise KeyError(link_id)
        rec = self.store.put(self.ns + "_link_review", {"item": link_id, "expert": user, "decision": decision,
                                                "wrong_kind": wrong_kind if decision == "uygun_degil" else "",
                                                "note": note, "at": now_iso()}, id=f"{user}:{link_id}", parent=user)
        self.store.audit(user, "pathway.link_review", link_id, {"decision": decision, "wrong_kind": wrong_kind})
        self._refresh_engine()
        return rec

    def path_queue(self, user: str) -> list[dict[str, Any]]:
        self.ensure_sample()
        mine = {r["item"]: r for r in self.store.list(self.ns + "_path_review", parent=user)}
        e = default_engine()
        self._refresh_engine()
        out = []
        for p in self.store.list(self.ns + "_path"):
            out.append({**p, "pathway": build(p["parsed"], e), "mine": mine.get(p["id"])})
        return out

    def review_path(self, user: str, path_id: str, decision: str, note: str = "") -> dict:
        if decision not in PATH_DECISIONS:
            raise ValueError("geçersiz karar")
        if decision == "uygun_degil" and not note.strip():
            raise ValueError("uygun değilse kısa gerekçe yazın")
        if not self.store.get(self.ns + "_path", path_id):
            raise KeyError(path_id)
        rec = self.store.put(self.ns + "_path_review", {"item": path_id, "expert": user, "decision": decision,
                                                "note": note, "at": now_iso()}, id=f"{user}:{path_id}", parent=user)
        self.store.audit(user, "pathway.path_review", path_id, {"decision": decision})
        return rec

    # consolidation, feedback and release gate
    def _final_links(self) -> dict[str, dict[str, Any]]:
        by: dict[str, list] = defaultdict(list)
        for r in self.store.list(self.ns + "_link_review"):
            by[r["item"]].append(r)
        final = {}
        need = int(self.thresholds().get("min_reviewers", 2))
        for item, rs in by.items():
            votes = [r for r in rs if r["decision"] != "emin_degilim"]
            c = Counter(r["decision"] for r in votes)
            if len(rs) < need:
                status = "değerlendirme sürüyor"      # a single expert never decides alone
            elif not votes:
                status = "belirsiz"
            elif c["uygun"] > c["uygun_degil"]:
                status = "onaylandı"
            elif c["uygun_degil"] > c["uygun"]:
                status = "reddedildi"
            else:
                status = "uyuşmazlık"
            kinds = Counter(r["wrong_kind"] for r in votes if r["decision"] == "uygun_degil")
            final[item] = {"status": status, "reviewers": len(rs), "votes": dict(c),
                           "wrong_kind": kinds.most_common(1)[0][0] if kinds else ""}
        return final

    def _refresh_engine(self) -> None:
        e = default_engine()
        rej, val = set(), set()
        for item, f in self._final_links().items():
            l = self.store.get(self.ns + "_link", item)
            if not l:
                continue
            key = frozenset((l["early_id"], l["late_id"]))
            if f["status"] == "reddedildi":
                rej.add(key)
            elif f["status"] == "onaylandı":
                val.add(key)
        e.set_reviews(rej, val)

    def summary(self) -> dict[str, Any]:
        self.ensure_sample()
        th = self.thresholds()
        all_links = self.store.list(self.ns + "_link")
        links = {l["id"]: l for l in all_links if l.get("origin", "rastgele") in ESTIMATE_ORIGINS}
        final = self._final_links()
        per_type = {}
        for t in ("tekrar", "temel", "ilişkili"):
            ids = [i for i, l in links.items() if l["type"] == t]
            dec = [final[i] for i in ids if i in final and final[i]["status"] in ("onaylandı", "reddedildi")
                   and final[i]["reviewers"] >= th["min_reviewers"]]
            ok = sum(1 for d in dec if d["status"] == "onaylandı")
            lo, hi = binomial_ci(ok, len(dec))
            rate = ok / len(dec) if dec else None
            census = t in CENSUS_TYPES and all(links[i].get("origin") == "tam" for i in ids)
            ci_ok = lo is not None and lo >= th["link_ci_lower_min"]
            if census:   # every link of this type is reviewed: the rate is exact, no interval needed
                enough = bool(ids) and len(dec) == len(ids)
                passed = enough and rate is not None and rate >= th["link_ok_min"]
                status = ("bu türde bağlantı yok" if not ids else
                          f"tümü inceleniyor ({len(dec)}/{len(ids)})" if not enough else
                          "eşik sağlandı" if passed else "eşik sağlanmadı")
            else:
                enough = len(dec) >= th["min_links_per_type"]
                passed = enough and rate is not None and rate >= th["link_ok_min"] and ci_ok
                status = ("kanıt yetersiz: müfredatta bu türden yalnız %d bağlantı var" % len(ids)
                          if len(ids) < th["min_links_per_type"] else
                          "değerlendirme sürüyor" if not enough else
                          "eşik sağlandı" if passed else "eşik sağlanmadı")
            per_type[t] = {"sampled": len(ids), "decided": len(dec), "ok": ok, "rate": rate, "ci95": [lo, hi],
                           "enough": enough, "status": status, "census": census, "met": bool(passed)}
        tek = [final[i] for i, l in links.items() if l["type"] == "tekrar" and i in final and final[i]["status"] in ("onaylandı", "reddedildi")]
        crit = sum(1 for d in tek if d["status"] == "reddedildi" and d["wrong_kind"] == "aslinda_yeni")
        crit_rate = crit / len(tek) if tek else None
        # agreement between the two most active experts on commonly reviewed links
        rv = self.store.list(self.ns + "_link_review")
        experts = [e for e, _ in Counter(r["expert"] for r in rv).most_common(2)]
        ac = {"n": 0, "ac1": None}
        if len(experts) == 2:
            a = {r["item"]: r["decision"] for r in rv if r["expert"] == experts[0]}
            b = {r["item"]: r["decision"] for r in rv if r["expert"] == experts[1]}
            common = sorted(set(a) & set(b))
            ac = agreement([a[i] for i in common], [b[i] for i in common], LINK_DECISIONS)
        # pathways
        pr = self.store.list(self.ns + "_path_review")
        by_path: dict[str, list] = defaultdict(list)
        for r in pr:
            by_path[r["item"]].append(r["decision"])
        path_final = {}
        for pid, ds in by_path.items():
            c = Counter(ds)
            good = c["uygun"] + c["kucuk_duzeltme"]
            path_final[pid] = good > c["uygun_degil"]
        n_paths = self.store.count(self.ns + "_path")
        path_rate = sum(path_final.values()) / len(path_final) if path_final else None
        conditions = {
            "links": all(v["met"] for v in per_type.values() if v["sampled"]),
            "critical": crit_rate is not None and crit_rate <= th["critical_max"],
            "paths": len(path_final) >= min(th["min_paths"], n_paths) and path_rate is not None and path_rate >= th["path_ok_min"],
            "agreement": (ac.get("ac1") is not None and ac["n"] >= th.get("min_common_for_agreement", 10)
                          and ac["ac1"] >= th["ac1_min"]),
        }
        reviewed_items = sum(1 for f in final.values() if f["status"] != "değerlendirme sürüyor")
        return {
            "thresholds": th, "per_type": per_type,
            "critical": {"count": crit, "of": len(tek), "rate": crit_rate},
            "agreement": {"experts": experts, **{k: ac.get(k) for k in ("n", "percent", "kappa", "ac1")}},
            "paths": {"sampled": n_paths, "reviewed": len(path_final), "ok_rate": path_rate},
            "origins": {o: {"label": ORIGINS[o], "total": sum(1 for l in all_links if l.get("origin", "rastgele") == o),
                            "decided": sum(1 for l in all_links if l.get("origin", "rastgele") == o and l["id"] in final
                                           and final[l["id"]]["status"] in ("onaylandı", "reddedildi"))}
                        for o in ORIGINS},
            "reports": self.store.count(self.ns + "_feedback"),
            "progress": {"links_total": len(all_links), "links_reviewed": reviewed_items,
                         "rejected": sum(1 for f in final.values() if f["status"] == "reddedildi"),
                         "confirmed": sum(1 for f in final.values() if f["status"] == "onaylandı"),
                         "disagreements": sum(1 for f in final.values() if f["status"] == "uyuşmazlık")},
            "conditions": conditions, "released": all(conditions.values()),
        }


def render_pathway(p: dict[str, Any], released: bool) -> str:
    head = ("_Uzman değerlendirmesinden geçmiş sürüm._" if released else
            "_Önizleme: bu özellik henüz uzman değerlendirmesinde; öneriler kesinleşmemiştir._")
    lines = [f"**{p['title']}**", head, ""]
    groups = [("once_tazele", "1) Önce tazele — yeni konulara geçmeden gözden geçir"),
              ("gerekli", "2) Gerekli — bu hedef için mutlaka çalış"),
              ("tekrar", "3) Tekrar — daha önce aynı düzeyde gördün, hızlı gözden geçir")]
    for key, title in groups:
        steps = [s for s in p["steps"] if s["label"] == key]
        # explained items (expert decisions, earlier basic level, rotation) before plain "first time here"
        steps.sort(key=lambda s: s["reason"].startswith("Bu içerik müfredatta ilk kez"))
        if not steps:
            continue
        lines.append(f"**{title}** ({len(steps)})")
        for s in steps[:25]:
            lines.append(f"- {s['topic']} [{s['block_id']}] — {s['reason']}")
        if len(steps) > 25:
            lines.append(f"- … ve {len(steps) - 25} konu daha")
        lines.append("")
    lines.append("_“Tekrar” atlama anlamına gelmez; konuyu hızlıca gözden geçirmen önerilir._")
    return "\n".join(lines)
