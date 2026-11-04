"""MİMAR — Synthetic MSKL demo data and simulated raters."""
from __future__ import annotations

import random
from itertools import combinations
from typing import Any

TOPICS: list[dict[str, str]] = [
    {"t": "rotator cuff", "anat": "the muscles of the rotator cuff, their attachments and innervation",
     "phys": "the role of the rotator cuff in dynamic stabilisation of the glenohumeral joint",
     "path": "the pathogenesis and classification of rotator cuff tears",
     "clin": "the clinical assessment of shoulder pain caused by rotator cuff disease"},
    {"t": "brachial plexus", "anat": "the formation, branches and relations of the brachial plexus",
     "phys": "the segmental innervation of upper limb muscles by the brachial plexus",
     "path": "the mechanisms of traction and compression injuries of the brachial plexus",
     "clin": "the neurological examination findings in brachial plexus injury"},
    {"t": "carpal tunnel", "anat": "the boundaries and contents of the carpal tunnel",
     "phys": "the sensory and motor distribution of the median nerve in the hand",
     "path": "the pathophysiology of median nerve compression at the wrist",
     "clin": "the diagnosis and management of carpal tunnel syndrome"},
    {"t": "bone remodeling", "anat": "the microscopic structure of compact and spongy bone",
     "phys": "the cellular mechanisms of bone remodeling by osteoblasts and osteoclasts",
     "path": "the pathogenesis of osteoporosis as an imbalance of bone remodeling",
     "clin": "the evaluation of fracture risk and bone mineral density in osteoporosis"},
    {"t": "calcium homeostasis", "anat": "the location and histology of the parathyroid glands",
     "phys": "the regulation of calcium and phosphate by parathyroid hormone and vitamin D",
     "path": "the mechanisms of rickets and osteomalacia due to vitamin D deficiency",
     "clin": "the clinical approach to a patient with hypocalcaemia and bone pain"},
    {"t": "fracture healing", "anat": "the periosteum and blood supply of long bones",
     "phys": "the stages of fracture healing and callus formation",
     "path": "the factors leading to delayed union and nonunion of fractures",
     "clin": "the principles of immobilisation and fixation in long bone fractures"},
    {"t": "skeletal muscle contraction", "anat": "the structure of the sarcomere and the neuromuscular junction",
     "phys": "the excitation–contraction coupling and the sliding filament mechanism in skeletal muscle",
     "path": "the pathophysiology of myasthenia gravis at the neuromuscular junction",
     "clin": "the clinical features and diagnostic tests of myasthenia gravis"},
    {"t": "muscular dystrophy", "anat": "the components of the dystrophin–glycoprotein complex of the muscle fibre",
     "phys": "the genetic basis of dystrophin production in skeletal muscle",
     "path": "the inheritance and molecular pathology of Duchenne muscular dystrophy",
     "clin": "the clinical presentation and multidisciplinary care of Duchenne muscular dystrophy"},
    {"t": "knee joint", "anat": "the ligaments, menisci and bursae of the knee joint",
     "phys": "the biomechanics of the knee during flexion, extension and rotation",
     "path": "the mechanisms of anterior cruciate ligament and meniscal injuries",
     "clin": "the physical examination of the knee including Lachman and McMurray tests"},
    {"t": "hip joint", "anat": "the articular surfaces, ligaments and blood supply of the hip joint",
     "phys": "the muscles acting on the hip during gait",
     "path": "the pathogenesis of avascular necrosis of the femoral head",
     "clin": "the management of hip fracture in older adults"},
    {"t": "developmental dysplasia of the hip", "anat": "the embryological development of the acetabulum and femoral head",
     "phys": "the normal development of hip stability in infancy",
     "path": "the risk factors and pathology of developmental dysplasia of the hip",
     "clin": "the neonatal screening of the hip with Ortolani and Barlow manoeuvres"},
    {"t": "vertebral column", "anat": "the structure of vertebrae and intervertebral discs",
     "phys": "the biomechanics of load transmission through the lumbar spine",
     "path": "the pathogenesis of intervertebral disc herniation",
     "clin": "the evaluation of low back pain and red flag findings"},
    {"t": "scoliosis", "anat": "the normal curvatures of the vertebral column",
     "phys": "the growth of the spine during adolescence",
     "path": "the classification and natural history of adolescent idiopathic scoliosis",
     "clin": "the screening and referral criteria for scoliosis in adolescents"},
    {"t": "osteoarthritis", "anat": "the structure of articular cartilage and synovial joints",
     "phys": "the biochemical composition and load bearing function of articular cartilage",
     "path": "the pathogenesis of cartilage degeneration in osteoarthritis",
     "clin": "the non-pharmacological and pharmacological management of knee osteoarthritis"},
    {"t": "rheumatoid arthritis", "anat": "the synovial membrane and joint capsule",
     "phys": "the cellular immune responses within the synovium",
     "path": "the immunopathogenesis of synovitis and pannus formation in rheumatoid arthritis",
     "clin": "the diagnosis and treatment strategy of rheumatoid arthritis using disease-modifying drugs"},
    {"t": "gout", "anat": "the typical joints affected by crystal arthropathies",
     "phys": "the metabolism and renal excretion of uric acid",
     "path": "the mechanisms of monosodium urate crystal deposition and inflammation",
     "clin": "the management of acute gout attacks and long-term urate lowering therapy"},
    {"t": "ankylosing spondylitis", "anat": "the sacroiliac joints and entheses",
     "phys": "the association between HLA-B27 and immune activation",
     "path": "the pathogenesis of enthesitis and spinal fusion in ankylosing spondylitis",
     "clin": "the clinical evaluation of inflammatory back pain"},
    {"t": "systemic lupus", "anat": "the connective tissue components affected in autoimmune diseases",
     "phys": "the mechanisms of immune tolerance and autoantibody production",
     "path": "the immune complex mediated tissue damage in systemic lupus erythematosus",
     "clin": "the musculoskeletal manifestations and laboratory evaluation of systemic lupus erythematosus"},
    {"t": "NSAIDs", "anat": "the distribution of cyclooxygenase enzymes in tissues",
     "phys": "the synthesis of prostaglandins in inflammation and pain",
     "path": "the mechanism of action and adverse effects of non-steroidal anti-inflammatory drugs",
     "clin": "the safe prescribing of non-steroidal anti-inflammatory drugs for musculoskeletal pain"},
    {"t": "bone tumours", "anat": "the zones of a growing long bone",
     "phys": "the growth plate activity during skeletal maturation",
     "path": "the histopathology of osteosarcoma and Ewing sarcoma",
     "clin": "the radiological red flags of a malignant bone lesion"},
    {"t": "osteomyelitis", "anat": "the metaphyseal vascular anatomy of long bones in children",
     "phys": "the host defence mechanisms of bone against bacteria",
     "path": "the pathogenesis of haematogenous osteomyelitis",
     "clin": "the diagnosis and antibiotic treatment of acute osteomyelitis"},
    {"t": "septic arthritis", "anat": "the joint capsule and synovial fluid spaces",
     "phys": "the composition and function of synovial fluid",
     "path": "the mechanisms of joint destruction in bacterial infection",
     "clin": "the emergency management of a hot swollen joint"},
    {"t": "gait", "anat": "the muscles of the lower limb involved in walking",
     "phys": "the phases of the normal gait cycle",
     "path": "the mechanisms of abnormal gait patterns after neurological injury",
     "clin": "the observational gait analysis in a rehabilitation setting"},
    {"t": "spinal cord injury", "anat": "the ascending and descending tracts of the spinal cord",
     "phys": "the spinal reflex arc and muscle tone regulation",
     "path": "the primary and secondary mechanisms of traumatic spinal cord injury",
     "clin": "the neurological classification and early rehabilitation of spinal cord injury"},
    {"t": "compartment syndrome", "anat": "the fascial compartments of the leg and forearm",
     "phys": "the relationship between tissue pressure and capillary perfusion",
     "path": "the pathophysiology of ischaemia in compartment syndrome",
     "clin": "the recognition and emergency fasciotomy decision in compartment syndrome"},
    {"t": "musculoskeletal imaging", "anat": "the radiographic anatomy of the shoulder, hip and knee",
     "phys": "the physical principles of radiography and magnetic resonance imaging of soft tissues",
     "path": "the imaging appearance of degenerative and inflammatory joint disease",
     "clin": "the selection of appropriate imaging for acute musculoskeletal trauma"},
]

FACET_YEAR = {"anat": 2, "phys": 2, "path": 3, "clin": 5}
FACET_VERBS = {"anat": ["Describe", "Identify", "Define", "List"],
               "phys": ["Explain", "Describe", "Summarize"],
               "path": ["Explain", "Discuss", "Describe"],
               "clin": ["Evaluate", "Manage", "Plan", "Interpret"]}

COURSES = {
    2: [("Y2-MSK-ANAT", "Musculoskeletal Anatomy", "Anatomy"),
        ("Y2-MSK-PHYS", "Physiology of Movement", "Physiology"),
        ("Y2-MSK-BIOC", "Biochemistry of Connective Tissue", "Biochemistry")],
    3: [("Y3-MSK-PATH", "Musculoskeletal Pathology", "Pathology"),
        ("Y3-MSK-PHAR", "Musculoskeletal Pharmacology", "Pharmacology"),
        ("Y3-MSK-RHEU", "Introduction to Rheumatology", "Internal Medicine")],
    5: [("Y5-ORTH", "Orthopaedics Clerkship", "Orthopaedics"),
        ("Y5-PMR", "Physical Medicine and Rehabilitation Clerkship", "PM&R"),
        ("Y5-RHEU", "Rheumatology Clerkship", "Internal Medicine")],
}

SYNONYMS = [("pathogenesis", "pathophysiology"), ("management", "treatment"),
            ("clinical assessment", "clinical evaluation"), ("mechanisms", "processes"),
            ("structure", "organisation"), ("muscles", "musculature"), ("innervation", "nerve supply"),
            ("diagnosis", "diagnostic work-up"), ("evaluation", "assessment"), ("injuries", "lesions"),
            ("injury", "lesion"), ("older adults", "elderly patients"), ("children", "paediatric patients"),
            ("clinical features", "signs and symptoms"), ("treatment", "therapeutic approach"),
            ("regulation", "control"), ("formation", "development"), ("classification", "categorisation"),
            ("examination", "clinical testing"), ("adverse effects", "side effects"), ("stages", "phases"),
            ("blood supply", "vascular supply"), ("relations", "anatomical relationships"),
            ("risk factors", "predisposing factors"), ("principles", "basic concepts")]

# Lexically similar but content-different objectives ("near misses")
NEAR_MISS_SWAPS = [("rotator cuff", "pelvic floor"), ("brachial plexus", "lumbosacral plexus"),
                   ("carpal tunnel", "tarsal tunnel"), ("median nerve", "tibial nerve"),
                   ("knee joint", "elbow joint"), ("hip joint", "shoulder joint"),
                   ("osteomyelitis", "cellulitis"), ("rheumatoid arthritis", "psoriatic arthritis"),
                   ("gout", "pseudogout"), ("leg and forearm", "hand and foot"),
                   ("osteosarcoma and Ewing sarcoma", "chondrosarcoma and giant cell tumour"),
                   ("Duchenne muscular dystrophy", "myotonic dystrophy"), ("myasthenia gravis", "Lambert–Eaton syndrome"),
                   ("femoral head", "scaphoid bone"), ("lumbar spine", "cervical spine"),
                   ("osteoporosis", "osteopetrosis"), ("parathyroid glands", "adrenal glands")]

FILLER = [
    "Describe the principles of informed consent before orthopaedic procedures.",
    "Explain the ethical issues in sports medicine practice.",
    "Discuss the role of the multidisciplinary team in chronic pain clinics.",
    "Describe occupational risk factors for work related musculoskeletal disorders.",
    "Explain the principles of evidence based physiotherapy referral.",
    "Identify the components of a structured handover in the orthopaedic ward.",
    "Discuss the burden of musculoskeletal disease in the national health system.",
    "Describe the safety principles of plaster cast application.",
]

UNCOVERED_UCEP = [
    ("Kemik iliği aspirasyonu endikasyonlarını açıklar", "Explain the indications for bone marrow aspiration", "Basic medical practice"),
    ("Fibromiyalji ön tanısını koyar", "Make a preliminary diagnosis of fibromyalgia", "Disease"),
    ("Polimiyozit ön tanısını koyar ve sevk eder", "Make a preliminary diagnosis of polymyositis and refer", "Disease"),
    ("Paget kemik hastalığını tanımlar", "Describe Paget disease of bone", "Disease"),
    ("Tortikolis değerlendirmesini yapar", "Assess torticollis", "Clinical presentation"),
    ("Topuk ağrısı ayırıcı tanısını yapar", "Perform the differential diagnosis of heel pain", "Clinical presentation"),
]


def _vary(phrase: str, rng: random.Random) -> str:
    """Stronger paraphrase: synonym substitution, optional truncation of a coordinated clause and re-framing."""
    for a, b in SYNONYMS:
        if a in phrase and rng.random() < 0.75:
            phrase = phrase.replace(a, b)
    if " and " in phrase and rng.random() < 0.3:
        head = phrase.split(" and ")[0]
        if len(head.split()) >= 5:          # only truncate when a meaningful clause remains
            phrase = head
    r = rng.random()
    if r < 0.25:
        phrase = f"{phrase} as encountered in patients"
    elif r < 0.4:
        phrase = f"key aspects of {phrase}"
    return phrase


def _lo_text(verb: str, phrase: str, rng: random.Random) -> str:
    style = rng.random()
    if style < 0.6:
        return f"{verb} {phrase}."
    if style < 0.85:
        return f"{verb} {phrase} in relation to clinical practice."
    return f"{verb} {phrase}, with examples."


def generate_mskl(seed: int = 20260913, overlap_rate: float = 0.55) -> dict[str, Any]:
    """Return {'los': [...], 'ucep': [...], 'truth': {...}} (truth is hidden simulation ground truth: overlap…"""
    rng = random.Random(seed)
    sessions: dict[str, int] = {}
    los: list[dict[str, Any]] = []
    group_of: dict[str, str] = {}
    facet_of: dict[str, str] = {}

    def add(year: int, course_idx: int, text: str, group: str, facet: str, ucep: list[str] | None = None):
        cid, cname, disc = COURSES[year][course_idx]
        sessions[cid] = sessions.get(cid, 0) + 1
        s_no = (sessions[cid] - 1) // 3 + 1          # ~3 LOs per session
        uid = f"SYN-{cid}-{sessions[cid]:03d}"
        los.append({"uid": uid, "text": text, "course": cname, "session": f"{cname} — Session {s_no}",
                    "activity": f"{cid}-S{s_no:02d}", "year": year, "term": "2026-2027",
                    "source": "SYNTHETIC (demo; not KUSOM data)", "discipline": disc,
                    "ucep_codes": ";".join(ucep or []), "mesh": "", "updated_at": "2026-09-01"})
        group_of[uid] = group
        facet_of[uid] = facet
        return uid

    ucep: list[dict[str, Any]] = []
    for ti, top in enumerate(TOPICS):
        code = f"SYN-UCEP-{ti + 1:03d}"
        ucep.append({"code": code, "text_tr": f"{top['t']} ile ilişkili kas-iskelet sorunlarını değerlendirir (sentetik)",
                     "text_en": f"Evaluate musculoskeletal problems related to {top['t']}; {top['clin']}",
                     "domain": "Disease", "mskl_scope": "1"})
        for facet in ("anat", "phys", "path", "clin"):
            year = FACET_YEAR[facet]
            primary = {"anat": 0, "phys": 1, "path": 0, "clin": 0}[facet]
            if facet == "phys" and ti % 3 == 0:
                primary = 2                          # some go to biochemistry
            if facet == "path" and ti % 4 == 1:
                primary = 2 if top["t"] in ("rheumatoid arthritis", "gout", "systemic lupus", "ankylosing spondylitis") else 1
            if facet == "clin" and ti % 3 == 1:
                primary = 1
            if facet == "clin" and top["t"] in ("rheumatoid arthritis", "gout", "systemic lupus", "ankylosing spondylitis"):
                primary = 2
            group = f"G{ti:02d}-{facet}"
            verb = rng.choice(FACET_VERBS[facet])
            link = [code] if facet == "clin" and rng.random() < 0.4 else []
            add(year, primary, _lo_text(verb, top[facet], rng), group, facet, link)
            if rng.random() < overlap_rate:
                # planted overlap: paraphrase in another course (same or later year)
                if rng.random() < 0.5:
                    y2, c2 = year, (primary + 1 + rng.randrange(2)) % 3
                else:
                    later = [y for y in (2, 3, 5) if y > year] or [year]
                    y2, c2 = rng.choice(later), rng.randrange(3)
                    if y2 == year and c2 == primary:
                        c2 = (c2 + 1) % 3
                v2 = rng.choice(FACET_VERBS[facet])
                add(y2, c2, _lo_text(v2, _vary(top[facet], rng), rng), group, facet)
                if rng.random() < 0.15:
                    y3 = rng.choice([2, 3, 5])
                    add(y3, rng.randrange(3), _lo_text(rng.choice(FACET_VERBS[facet]), _vary(top[facet], rng), rng),
                        group, facet)
    # near-miss negatives: lexically close, different content
    nm = 0
    for ti, top in enumerate(TOPICS):
        for facet in ("anat", "phys", "path", "clin"):
            for a, b in NEAR_MISS_SWAPS:
                if a in top[facet] and rng.random() < 0.45:
                    year = FACET_YEAR[facet]
                    add(year, rng.randrange(3), _lo_text(rng.choice(FACET_VERBS[facet]), top[facet].replace(a, b), rng),
                        f"NM-{nm:03d}", facet)
                    nm += 1
                    break
    for i, f in enumerate(FILLER):
        y = (2, 3, 5)[i % 3]
        add(y, i % 3, f, f"FILL-{i}", "filler")
    uncovered = []
    for j, (tr, en, dom) in enumerate(UNCOVERED_UCEP, start=1):
        code = f"SYN-UCEP-U{j:02d}"
        uncovered.append(code)
        ucep.append({"code": code, "text_tr": f"{tr} (sentetik)", "text_en": en, "domain": dom, "mskl_scope": "1"})
    ucep.append({"code": "SYN-UCEP-X01", "text_tr": "Akut koroner sendrom ön tanısını koyar (sentetik, MSKL dışı)",
                 "text_en": "Make a preliminary diagnosis of acute coronary syndrome", "domain": "Disease",
                 "mskl_scope": "0"})
    rng.shuffle(los)
    return {"los": los, "ucep": ucep,
            "truth": {"group_of": group_of, "facet_of": facet_of, "uncovered_ucep": uncovered,
                      "note": "Simulation ground truth — admin only; never shown to reviewers."}}


def true_overlap(truth: dict[str, Any], a: str, b: str) -> bool:
    g = truth["group_of"]
    return g.get(a) is not None and g.get(a) == g.get(b) and not g[a].startswith("FILL")


def simulated_label(truth: dict[str, Any], a: str, b: str, reviewer_seed: int, error_rate: float = 0.06,
                    insufficient_rate: float = 0.01) -> str:
    """Deterministic noisy rater: 'overlap' | 'no_overlap' | 'insufficient'."""
    rng = random.Random(f"{reviewer_seed}|{a}|{b}")
    if rng.random() < insufficient_rate:
        return "insufficient"
    t = true_overlap(truth, a, b)
    if rng.random() < error_rate:
        t = not t
    return "overlap" if t else "no_overlap"


def simulated_expert_findings(truth: dict[str, Any], los: list[dict[str, Any]], seed: int = 7,
                              recall: float = 0.6) -> list[dict[str, Any]]:
    """Expert–Core report imitation: experts find a share of true same-level repetitions, most true UÇEP gaps and…"""
    rng = random.Random(seed)
    by_group: dict[str, list[dict[str, Any]]] = {}
    for lo in los:
        by_group.setdefault(truth["group_of"][lo["uid"]], []).append(lo)
    out = []
    for g, members in sorted(by_group.items()):
        if len(members) < 2 or g.startswith("FILL"):
            continue
        if rng.random() < recall:
            out.append({"category": "redundancy", "los": sorted(m["uid"] for m in members),
                        "statement": "The same content appears in several courses at a similar level.",
                        "rationale": "Repetition does not appear to add depth; consider consolidating."})
    for code in truth["uncovered_ucep"]:
        if rng.random() < 0.8:
            out.append({"category": "gap_ucep", "ucep": [code],
                        "statement": f"No MSKL objective clearly corresponds to {code}.",
                        "rationale": "Check whether this item should be addressed within MSKL."})
    # a few integration ideas
    groups = sorted({g.split('-')[0] for g in by_group if not g.startswith("FILL")})
    for gi in rng.sample(groups, min(5, len(groups))):
        a = by_group.get(f"{gi}-anat"); c = by_group.get(f"{gi}-clin")
        if a and c:
            out.append({"category": "integration", "los": sorted([a[0]["uid"], c[0]["uid"]]),
                        "statement": "Anatomy and clinical objectives on the same topic could be explicitly linked.",
                        "rationale": "A shared clinical case could connect basic and clinical learning."})
    return out


def simulated_validation(truth: dict[str, Any], entry: dict[str, Any], validator_seed: int,
                         error_rate: float = 0.07) -> dict[str, str]:
    """Imitates a validator's three-part decision for a blinded entry."""
    rng = random.Random(f"{validator_seed}|{entry['code']}")
    cat = entry["category"]
    los = entry["items"].get("los", [])
    if cat == "redundancy":
        groups = {truth["group_of"].get(u) for u in los}
        ok = len(groups) == 1 and len(los) >= 2
    elif cat == "gap_ucep":
        ok = all(c in truth["uncovered_ucep"] for c in entry["items"].get("ucep", []))
    else:
        tops = {truth["group_of"].get(u, "x").split("-")[0] for u in los}
        ok = len(tops) == 1
    if rng.random() < error_rate:
        ok = not ok
    support = "yes" if ok or rng.random() < 0.5 else "no"
    meaningful = "yes" if ok else "no"
    if rng.random() < 0.02:
        support = "insufficient"
    return {"support": support, "meaningful": meaningful, "category_ok": "yes" if rng.random() > 0.05 else "no"}
