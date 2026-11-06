"""
CURATOR — Koç University School of Medicine Curriculum
Canonical static knowledge base for Year 1–6.

This module is the single source of truth until a full PDF ingestion
pipeline (WP1) populates Neo4j from official syllabi.
Each block entry is used to:
  - seed Neo4j (graph relationships)
  - build FAISS vector index (semantic retrieval)
  - populate BM25 index (keyword retrieval)
"""
from __future__ import annotations

from typing import Any

#  Curriculum Definition

KUC_CURRICULUM: list[dict[str, Any]] = [
    # YEAR 1
    {
        "year": 1,
        "name_en": "Year 1 — Foundations",
        "name_tr": "1. Yıl — Temeller",
        "description_en": "Foundational sciences: cell biology, genetics, anatomy, biochemistry, and biophysics.",
        "description_tr": "Temel bilimler: hücre biyolojisi, genetik, anatomi, biyokimya ve biyofizik.",
        "blocks": [
            {
                "id": "Y1B1",
                "block_number": 1,
                "name_en": "Introduction to Medicine",
                "name_tr": "Tıbba Giriş",
                "weeks": "1–4",
                "departments": ["History of Medicine and Ethics"],
                "topics": [
                    "history of medicine", "medical ethics", "doctor-patient relationship",
                    "evidence-based medicine", "professionalism", "study skills",
                    "healthcare systems in Turkey", "hipokrat yemini",
                ],
                "competencies": ["Professionalism", "Communication", "Scientific Inquiry"],
                "prerequisite_ids": [],
                "description_en": (
                    "Introduction to the medical profession, its history and ethical foundations. "
                    "Topics include: history of medicine from antiquity to modern times, medical ethics "
                    "and the Hippocratic tradition, doctor-patient communication, evidence-based medicine "
                    "principles, professionalism, and an overview of the Turkish healthcare system."
                ),
                "description_tr": (
                    "Tıp mesleğine, tarihine ve etik temellerine giriş. Konular: antik çağdan günümüze "
                    "tıp tarihi, tıp etiği ve Hipokrat geleneği, hekim-hasta iletişimi, kanıta dayalı "
                    "tıp ilkeleri, profesyonellik ve Türk sağlık sistemi genel görünümü."
                ),
            },
            {
                "id": "Y1B2",
                "block_number": 2,
                "name_en": "Cell Biology, Genetics & Molecular Biology",
                "name_tr": "Hücre Biyolojisi, Genetik ve Moleküler Biyoloji",
                "weeks": "5–12",
                "departments": ["Medical Biology", "Histology and Embryology"],
                "topics": [
                    "cell structure", "cell membrane", "nucleus", "organelles",
                    "cell cycle", "mitosis", "meiosis", "DNA structure", "DNA replication",
                    "transcription", "translation", "gene expression regulation",
                    "Mendelian genetics", "chromosomal disorders", "Down syndrome",
                    "molecular biology techniques", "PCR", "gel electrophoresis",
                    "stem cells", "apoptosis", "cancer biology basics",
                ],
                "competencies": ["Medical Knowledge", "Scientific Inquiry"],
                "prerequisite_ids": [],
                "description_en": (
                    "Core molecular and cellular biology underpinning all clinical medicine. "
                    "Cell structure and organelle function; cell cycle regulation and division; "
                    "DNA replication, transcription and translation; Mendelian and chromosomal genetics; "
                    "common chromosomal disorders (trisomies, deletions); molecular techniques "
                    "used in diagnosis (PCR, FISH, karyotyping); stem cell biology and cancer basics."
                ),
                "description_tr": (
                    "Tüm klinik tıbbın temelini oluşturan moleküler ve hücresel biyoloji. "
                    "Hücre yapısı ve organel işlevleri; hücre döngüsü düzenlemesi; DNA replikasyonu, "
                    "transkripsiyon ve translasyon; Mendel ve kromozomal genetik; "
                    "yaygın kromozomal bozukluklar (trizomiler, delesyonlar); "
                    "tanıda kullanılan moleküler teknikler; kök hücre biyolojisi ve kanser temelleri."
                ),
            },
            {
                "id": "Y1B3",
                "block_number": 3,
                "name_en": "Locomotor System & Gross Anatomy I",
                "name_tr": "Hareket Sistemi ve Gross Anatomi I",
                "weeks": "13–20",
                "departments": ["Anatomy", "Physiology", "Histology and Embryology"],
                "topics": [
                    "upper extremity anatomy", "shoulder anatomy", "brachial plexus",
                    "lower extremity anatomy", "hip joint", "knee joint", "ankle",
                    "spine anatomy", "vertebral column", "spinal cord anatomy",
                    "bone histology", "cartilage histology", "joint types",
                    "muscle physiology", "muscle contraction", "neuromuscular junction",
                    "embryology of limbs", "common anatomical variants",
                ],
                "competencies": ["Medical Knowledge", "Patient Care"],
                "prerequisite_ids": ["Y1B2"],
                "description_en": (
                    "Regional anatomy of the locomotor system with cadaveric and prosection work. "
                    "Upper extremity: shoulder, elbow, forearm, wrist and hand; brachial plexus and "
                    "peripheral nerves. Lower extremity: hip, thigh, leg, foot; lumbosacral plexus. "
                    "Vertebral column and back muscles. Bone and cartilage histology. "
                    "Muscle physiology: sliding filament theory, neuromuscular junction, "
                    "excitation-contraction coupling."
                ),
                "description_tr": (
                    "Kadavra çalışması ile hareket sisteminin bölgesel anatomisi. "
                    "Üst ekstremite: omuz, dirsek, önkol, el bileği ve el; brakiyal pleksus. "
                    "Alt ekstremite: kalça, uyluk, bacak, ayak; lumbosakral pleksus. "
                    "Vertebral kolon ve sırt kasları. Kemik ve kıkırdak histolojisi. "
                    "Kas fizyolojisi: kayan filaman teorisi, nöromüsküler kavşak."
                ),
            },
            {
                "id": "Y1B4",
                "block_number": 4,
                "name_en": "Biochemistry & Biophysics",
                "name_tr": "Biyokimya ve Biyofizik",
                "weeks": "21–28",
                "departments": ["Medical Biochemistry", "Biophysics"],
                "topics": [
                    "carbohydrate metabolism", "glycolysis", "Krebs cycle", "oxidative phosphorylation",
                    "gluconeogenesis", "glycogen metabolism",
                    "lipid metabolism", "fatty acid synthesis", "beta-oxidation", "ketone bodies",
                    "cholesterol biosynthesis", "lipoprotein metabolism",
                    "protein structure", "amino acid metabolism", "enzyme kinetics",
                    "Michaelis-Menten", "enzyme inhibition", "bioenergetics", "ATP",
                    "membrane biophysics", "membrane potential", "ion channels",
                    "cellular signalling", "second messengers", "cAMP", "calcium signalling",
                    "vitamins", "cofactors", "metabolic disorders", "inborn errors of metabolism",
                ],
                "competencies": ["Medical Knowledge", "Scientific Inquiry"],
                "prerequisite_ids": ["Y1B2"],
                "description_en": (
                    "Metabolic and biophysical foundations of human physiology. "
                    "Carbohydrate metabolism: glycolysis, TCA cycle, oxidative phosphorylation, "
                    "gluconeogenesis. Lipid metabolism: fatty acid oxidation and synthesis, "
                    "lipoprotein metabolism, cholesterol. Protein and amino acid metabolism. "
                    "Enzyme kinetics. Bioenergetics. Membrane biophysics: resting membrane potential, "
                    "ion channels, action potential basics. Cellular signalling pathways. "
                    "Clinically relevant metabolic disorders."
                ),
                "description_tr": (
                    "İnsan fizyolojisinin metabolik ve biyofiziksel temelleri. "
                    "Karbonhidrat metabolizması: glikoliz, TCA döngüsü, oksidatif fosforilasyon. "
                    "Lipit metabolizması: yağ asidi oksidasyonu ve sentezi, kolesterol. "
                    "Protein ve amino asit metabolizması. Enzim kinetiği. Biyoenerjetik. "
                    "Zar biyofiziği: dinlenim membran potansiyeli, iyon kanalları. "
                    "Hücresel sinyal yolakları. Klinik açıdan önemli metabolik bozukluklar."
                ),
            },
            {
                "id": "Y1VI",
                "block_number": 5,
                "name_en": "Vertical Integration — Year 1",
                "name_tr": "Dikey Entegrasyon — 1. Yıl",
                "weeks": "1–28 (parallel)",
                "departments": ["Medical Statistics", "History of Medicine and Ethics"],
                "topics": [
                    "clinical skills basics", "physical examination introduction",
                    "communication skills", "medical statistics", "biostatistics",
                    "epidemiology basics", "study design", "p-values", "confidence intervals",
                    "ethics seminars", "reflective practice",
                ],
                "competencies": ["Communication", "Professionalism", "Scientific Inquiry"],
                "prerequisite_ids": [],
                "description_en": (
                    "Longitudinal Year 1 vertical integration strand. "
                    "Clinical Skills I: introduction to history-taking and physical examination. "
                    "Medical Statistics: descriptive statistics, hypothesis testing, study design, "
                    "reading and critically appraising medical literature. "
                    "Ethics Seminar Series: professional dilemmas, informed consent, confidentiality."
                ),
                "description_tr": (
                    "1. Yıl dikey entegrasyon bileşeni. "
                    "Klinik Beceriler I: anamnez alma ve fizik muayeneye giriş. "
                    "Tıbbi İstatistik: tanımlayıcı istatistik, hipotez testi, çalışma tasarımı, "
                    "tıbbi literatür değerlendirmesi. "
                    "Etik Seminer Serisi: profesyonel ikilemler, aydınlatılmış onam, gizlilik."
                ),
            },
        ],
    },

    # YEAR 2
    {
        "year": 2,
        "name_en": "Year 2 — Organ Systems I",
        "name_tr": "2. Yıl — Organ Sistemleri I",
        "description_en": "Cardiovascular, respiratory, haematological, and renal systems.",
        "description_tr": "Kardiyovasküler, solunum, hematolojik ve renal sistemler.",
        "blocks": [
            {
                "id": "Y2B1",
                "block_number": 1,
                "name_en": "Cardiovascular System",
                "name_tr": "Kardiyovasküler Sistem",
                "weeks": "1–8",
                "departments": ["Cardiology", "Physiology", "Medical Pharmacology", "Anatomy"],
                "topics": [
                    "cardiac anatomy", "pericardium", "heart chambers",
                    "cardiac electrophysiology", "action potential", "ECG interpretation",
                    "cardiac cycle", "Starling's law", "preload afterload",
                    "hemodynamics", "blood pressure regulation",
                    "heart failure", "systolic diastolic dysfunction",
                    "coronary artery disease", "angina", "myocardial infarction",
                    "arrhythmias", "atrial fibrillation", "ventricular tachycardia",
                    "hypertension", "valvular heart disease", "aortic stenosis", "mitral regurgitation",
                    "peripheral vascular disease", "deep vein thrombosis",
                    "cardiac pharmacology", "antihypertensives", "antiarrhythmics",
                    "anticoagulants", "statins",
                    "cardiac auscultation", "heart sounds", "murmurs",
                ],
                "competencies": ["Medical Knowledge", "Patient Care", "Clinical Reasoning"],
                "prerequisite_ids": ["Y1B3", "Y1B4"],
                "description_en": (
                    "Comprehensive cardiovascular medicine block. "
                    "Anatomy of the heart and great vessels. Electrophysiology and ECG interpretation: "
                    "normal ECG, common arrhythmias (AF, flutter, VT, heart blocks). "
                    "Cardiac cycle and haemodynamics. Heart failure: pathophysiology, classification, "
                    "management. Coronary artery disease: risk factors, angina, acute MI, "
                    "reperfusion strategies. Hypertension: classification, end-organ damage, treatment. "
                    "Valvular disease. Cardiac pharmacology: ACE inhibitors, beta-blockers, "
                    "diuretics, antiarrhythmics, statins, anticoagulants."
                ),
                "description_tr": (
                    "Kapsamlı kardiyovasküler tıp bloğu. "
                    "Kalp ve büyük damarların anatomisi. Elektrofizyoloji ve EKG yorumlama: "
                    "normal EKG, yaygın aritmiler (AF, flutter, VT, kalp blokları). "
                    "Kardiyak döngü ve hemodinamik. Kalp yetmezliği: patofizyoloji, sınıflama, tedavi. "
                    "Koroner arter hastalığı: risk faktörleri, anjina, akut MI, reperfüzyon. "
                    "Hipertansiyon: sınıflama, hedef organ hasarı, tedavi. "
                    "Kapak hastalıkları. Kardiyak farmakoloji."
                ),
            },
            {
                "id": "Y2B2",
                "block_number": 2,
                "name_en": "Respiratory System",
                "name_tr": "Solunum Sistemi",
                "weeks": "9–14",
                "departments": ["Pulmonary Medicine", "Physiology", "Medical Pharmacology"],
                "topics": [
                    "pulmonary anatomy", "airways", "alveoli",
                    "lung volumes", "spirometry", "FEV1 FVC",
                    "gas exchange", "ventilation-perfusion", "diffusion",
                    "respiratory mechanics", "compliance", "resistance",
                    "control of breathing", "respiratory centres",
                    "obstructive lung disease", "asthma", "COPD", "bronchiectasis",
                    "restrictive lung disease", "interstitial lung disease", "fibrosis",
                    "pulmonary infections", "pneumonia", "tuberculosis", "COVID-19",
                    "lung cancer", "pleural disease", "pneumothorax", "pleural effusion",
                    "respiratory pharmacology", "bronchodilators", "corticosteroids",
                    "arterial blood gas interpretation",
                ],
                "competencies": ["Medical Knowledge", "Patient Care"],
                "prerequisite_ids": ["Y2B1"],
                "description_en": (
                    "Anatomy and physiology of the respiratory system followed by major diseases. "
                    "Lung volumes and capacities; spirometry and peak flow measurement; gas exchange "
                    "and acid-base balance; ABG interpretation. Obstructive diseases: asthma "
                    "(pathophysiology, triggers, stepwise management) and COPD. "
                    "Pneumonia: CAP, HAP, atypical; tuberculosis. Lung cancer: staging, types. "
                    "Respiratory pharmacology: beta-agonists, anticholinergics, inhaled corticosteroids, "
                    "antibiotics."
                ),
                "description_tr": (
                    "Solunum sisteminin anatomisi ve fizyolojisi ardından başlıca hastalıklar. "
                    "Akciğer hacimleri ve kapasiteleri; spirometri; gaz değişimi ve asit-baz dengesi; "
                    "arter kan gazı yorumlama. Obstrüktif hastalıklar: astım ve KOAH. "
                    "Pnömoni: KAP, HAP, atipik; tüberküloz. Akciğer kanseri. "
                    "Solunum farmakolojisi."
                ),
            },
            {
                "id": "Y2B3",
                "block_number": 3,
                "name_en": "Haematology & Lymphoid System",
                "name_tr": "Hematoloji ve Lenfoid Sistem",
                "weeks": "15–19",
                "departments": ["Internal Medicine", "Medical Biology", "Medical Pharmacology"],
                "topics": [
                    "haematopoiesis", "bone marrow", "blood cell development",
                    "red cell disorders", "iron deficiency anaemia", "B12 deficiency",
                    "haemolytic anaemia", "sickle cell disease", "thalassaemia",
                    "white cell disorders", "neutropenia", "leukocytosis",
                    "lymphoma", "Hodgkin lymphoma", "non-Hodgkin lymphoma",
                    "leukaemia", "ALL", "AML", "CLL", "CML",
                    "multiple myeloma", "plasma cell disorders",
                    "coagulation cascade", "bleeding disorders",
                    "haemophilia", "Von Willebrand disease",
                    "thrombocytopenia", "ITP", "TTP",
                    "blood transfusion", "blood groups", "ABO system",
                    "anticoagulants", "warfarin", "heparin", "DOACs",
                ],
                "competencies": ["Medical Knowledge", "Patient Care"],
                "prerequisite_ids": ["Y1B2"],
                "description_en": (
                    "Haematopoiesis and the lymphoid system, followed by clinical haematology. "
                    "Red cell disorders: iron deficiency, megaloblastic, haemolytic anaemias including "
                    "sickle cell disease and thalassaemia. White cell disorders and lymphomas. "
                    "Leukaemias: ALL, AML, CLL, CML — classification, staging, treatment principles. "
                    "Multiple myeloma. Coagulation: cascade, bleeding disorders (haemophilia, vWD), "
                    "thrombocytopenia. Blood transfusion and blood groups. "
                    "Anticoagulant therapy: heparin, warfarin, DOACs."
                ),
                "description_tr": (
                    "Hematopoez ve lenfoid sistem ardından klinik hematoloji. "
                    "Eritrosit bozuklukları: demir eksikliği, megaloblastik, hemolitik anemiler. "
                    "Lenfomalar. Lösemiler: ALL, AML, KLL, KML. Multipl miyelom. "
                    "Koagülasyon: kanama bozuklukları, trombositopeni. "
                    "Kan transfüzyonu ve kan grupları. Antikoagülan tedavi."
                ),
            },
            {
                "id": "Y2B4",
                "block_number": 4,
                "name_en": "Renal & Urinary System",
                "name_tr": "Renal ve Üriner Sistem",
                "weeks": "20–24",
                "departments": ["Internal Medicine", "Physiology", "Medical Pharmacology"],
                "topics": [
                    "kidney anatomy", "nephron anatomy", "glomerulus",
                    "renal physiology", "GFR", "tubular secretion reabsorption",
                    "urine concentration dilution", "renin-angiotensin-aldosterone",
                    "glomerular diseases", "IgA nephropathy", "nephrotic syndrome",
                    "nephritic syndrome", "FSGS",
                    "acute kidney injury", "AKI", "prerenal intrinsic postrenal",
                    "chronic kidney disease", "CKD", "dialysis", "renal replacement therapy",
                    "urinary tract infections", "cystitis", "pyelonephritis",
                    "renal calculi", "nephrolithiasis",
                    "renal pharmacology", "diuretics", "ACE inhibitors renal",
                    "fluid and electrolyte balance", "hyponatraemia", "hyperkalaemia",
                    "acid-base disorders", "metabolic acidosis", "metabolic alkalosis",
                ],
                "competencies": ["Medical Knowledge", "Patient Care"],
                "prerequisite_ids": ["Y1B4"],
                "description_en": (
                    "Structure and function of the kidney followed by renal pathology. "
                    "Nephron physiology: GFR, tubular functions, concentration mechanisms, RAAS. "
                    "Fluid and electrolyte balance; acid-base disorders and interpretation. "
                    "Glomerular diseases: nephrotic and nephritic syndromes. "
                    "AKI: classification and management. CKD: staging, complications, "
                    "renal replacement therapy. Urinary tract infections; renal calculi. "
                    "Renal pharmacology: diuretics, ACE inhibitors/ARBs."
                ),
                "description_tr": (
                    "Böbreğin yapısı ve işlevi ardından renal patoloji. "
                    "Nefron fizyolojisi: GFR, tübüler fonksiyonlar, konsantrasyon mekanizmaları. "
                    "Sıvı-elektrolit dengesi; asit-baz bozuklukları. "
                    "Glomerüler hastalıklar: nefrotik ve nefritik sendromlar. "
                    "ABY: sınıflama ve yönetim. KBH: evreleme, komplikasyonlar, renal replasman tedavisi. "
                    "İdrar yolu enfeksiyonları; renal taşlar. Diüretikler, ACE inhibitörleri."
                ),
            },
            {
                "id": "Y2VI",
                "block_number": 5,
                "name_en": "Vertical Integration — Year 2",
                "name_tr": "Dikey Entegrasyon — 2. Yıl",
                "weeks": "1–24 (parallel)",
                "departments": ["Radiology", "Medical Pharmacology"],
                "topics": [
                    "clinical skills II", "cardiovascular examination", "respiratory examination",
                    "abdominal examination", "ECG reading workshop",
                    "radiology basics", "chest X-ray", "CT interpretation basics",
                    "pharmacology principles", "drug prescribing",
                ],
                "competencies": ["Patient Care", "Communication", "Medical Knowledge"],
                "prerequisite_ids": ["Y1VI"],
                "description_en": (
                    "Year 2 vertical integration strand. Clinical Skills II: systematic physical "
                    "examination of cardiovascular and respiratory systems; abdominal examination. "
                    "ECG interpretation workshops. Radiology Basics: chest X-ray interpretation, "
                    "introduction to CT chest and abdomen. Pharmacology: principles of prescribing, "
                    "adverse drug reactions, polypharmacy."
                ),
                "description_tr": (
                    "2. Yıl dikey entegrasyon bileşeni. Klinik Beceriler II: kardiyovasküler ve solunum "
                    "sisteminin sistematik fizik muayenesi; abdominal muayene. "
                    "EKG yorumlama atölyeleri. Radyoloji Temelleri: akciğer grafisi yorumlama, "
                    "BT'ye giriş. Farmakoloji: ilaç reçetelemesi ilkeleri."
                ),
            },
        ],
    },

    # YEAR 3
    {
        "year": 3,
        "name_en": "Year 3 — Organ Systems II",
        "name_tr": "3. Yıl — Organ Sistemleri II",
        "description_en": "Nervous system, GI, endocrine, musculoskeletal, dermatology, and clinical introduction.",
        "description_tr": "Sinir sistemi, GI, endokrin, kas-iskelet, dermatoloji ve klinik giriş.",
        "blocks": [
            {
                "id": "Y3B1",
                "block_number": 1,
                "name_en": "Nervous System & Psychiatry",
                "name_tr": "Sinir Sistemi ve Psikiyatri",
                "weeks": "1–9",
                "departments": ["Neurology", "Psychiatry", "Anatomy"],
                "topics": [
                    "neuroanatomy", "cerebral cortex", "brainstem", "cerebellum",
                    "basal ganglia", "limbic system", "spinal cord tracts",
                    "cranial nerves", "autonomic nervous system",
                    "stroke", "ischaemic stroke", "haemorrhagic stroke",
                    "TIA", "thrombolysis", "stroke rehabilitation",
                    "epilepsy", "seizure types", "antiepileptics",
                    "Parkinson disease", "movement disorders", "tremor",
                    "dementia", "Alzheimer disease", "vascular dementia",
                    "multiple sclerosis", "headache", "migraine",
                    "peripheral neuropathy", "Guillain-Barre",
                    "depression", "major depressive disorder", "antidepressants",
                    "anxiety disorders", "GAD", "panic disorder",
                    "bipolar disorder", "mood stabilisers",
                    "schizophrenia", "antipsychotics",
                    "substance use disorders",
                    "sleep disorders",
                ],
                "competencies": ["Medical Knowledge", "Patient Care", "Communication"],
                "prerequisite_ids": ["Y1B3", "Y2B1"],
                "description_en": (
                    "Integrated neuroscience and psychiatry block. "
                    "Neuroanatomy: cerebral hemispheres, brainstem, cerebellum, basal ganglia, "
                    "spinal cord, cranial nerves, autonomic nervous system. "
                    "Stroke: ischaemic and haemorrhagic, thrombolysis, secondary prevention. "
                    "Epilepsy: seizure classification and management. "
                    "Parkinson disease and movement disorders. Dementia: Alzheimer, vascular, Lewy body. "
                    "Headache syndromes. Peripheral neuropathy. "
                    "Psychiatry: depression, anxiety disorders, bipolar disorder, schizophrenia, "
                    "substance use disorders. Psychopharmacology."
                ),
                "description_tr": (
                    "Entegre nörobilim ve psikiyatri bloğu. "
                    "Nöroanatomi: serebral hemisferler, beyin sapı, serebelum, bazal gangliyonlar, "
                    "spinal kord, kranyal sinirler, otonom sinir sistemi. "
                    "İnme: iskemik ve hemorajik, trombolitik tedavi. "
                    "Epilepsi: nöbet sınıflandırması ve yönetimi. "
                    "Parkinson hastalığı ve hareket bozuklukları. Demans. "
                    "Psikiyatri: depresyon, anksiyete bozuklukları, bipolar bozukluk, şizofreni. "
                    "Psikofarmakoloji."
                ),
            },
            {
                "id": "Y3B2",
                "block_number": 2,
                "name_en": "Gastrointestinal & Hepatobiliary System",
                "name_tr": "Gastrointestinal ve Hepatobiliyer Sistem",
                "weeks": "10–15",
                "departments": ["Internal Medicine", "General Surgery", "Anatomy"],
                "topics": [
                    "GI anatomy", "oesophagus", "stomach", "small bowel", "large bowel",
                    "liver anatomy", "biliary system", "pancreas",
                    "oesophageal diseases", "GORD", "Barrett oesophagus",
                    "peptic ulcer disease", "H pylori",
                    "inflammatory bowel disease", "Crohn disease", "ulcerative colitis",
                    "irritable bowel syndrome", "colorectal cancer",
                    "liver diseases", "viral hepatitis", "hepatitis B", "hepatitis C",
                    "alcoholic liver disease", "NAFLD", "cirrhosis", "portal hypertension",
                    "hepatocellular carcinoma",
                    "biliary disease", "gallstones", "cholecystitis", "cholangitis",
                    "pancreatitis", "acute pancreatitis", "chronic pancreatitis", "pancreatic cancer",
                    "GI pharmacology", "proton pump inhibitors", "antiemetics",
                ],
                "competencies": ["Medical Knowledge", "Patient Care"],
                "prerequisite_ids": ["Y1B3"],
                "description_en": (
                    "Gastrointestinal tract from oesophagus to rectum and hepatobiliary system. "
                    "GORD and Barrett oesophagus; peptic ulcer disease and H. pylori eradication. "
                    "Inflammatory bowel disease: Crohn's and UC, medical and surgical management. "
                    "Colorectal cancer: screening, staging, treatment. "
                    "Hepatology: viral hepatitis (B and C), alcoholic and non-alcoholic fatty liver, "
                    "cirrhosis complications (varices, ascites, HE), HCC. "
                    "Biliary: gallstones, cholecystitis, ERCP. "
                    "Pancreatitis: Ranson criteria, management; pancreatic cancer."
                ),
                "description_tr": (
                    "Özofagustan rektuma gastrointestinal sistem ve hepatobiliyer sistem. "
                    "GÖRH ve Barrett özofagus; peptik ülser hastalığı ve H. pylori eradikasyonu. "
                    "İnflamatuvar barsak hastalığı: Crohn ve ÜK, tıbbi ve cerrahi yönetim. "
                    "Kolorektal kanser: tarama, evreleme, tedavi. "
                    "Hepatoloji: viral hepatit (B ve C), alkolik ve nonalkolik yağlı karaciğer, "
                    "siroz komplikasyonları, HCC. Biliyer sistem. Pankreatit ve pankreas kanseri."
                ),
            },
            {
                "id": "Y3B3",
                "block_number": 3,
                "name_en": "Endocrine & Metabolic System",
                "name_tr": "Endokrin ve Metabolik Sistem",
                "weeks": "16–20",
                "departments": ["Internal Medicine", "Medical Biochemistry"],
                "topics": [
                    "hypothalamic-pituitary axis", "pituitary adenoma",
                    "thyroid anatomy", "thyroid physiology", "hypothyroidism", "Hashimoto",
                    "hyperthyroidism", "Graves disease", "thyroid cancer",
                    "adrenal gland", "adrenal cortex", "glucocorticoids",
                    "Addison disease", "Cushing syndrome", "primary hyperaldosteronism",
                    "phaeochromocytoma",
                    "diabetes mellitus", "type 1 diabetes", "type 2 diabetes",
                    "insulin therapy", "oral hypoglycaemics", "metformin",
                    "diabetic ketoacidosis", "HHS", "hypoglycaemia",
                    "diabetic complications", "retinopathy", "nephropathy", "neuropathy",
                    "metabolic syndrome", "obesity",
                    "calcium metabolism", "hyperparathyroidism", "hypoparathyroidism",
                    "osteoporosis", "Paget disease",
                ],
                "competencies": ["Medical Knowledge", "Patient Care"],
                "prerequisite_ids": ["Y1B4"],
                "description_en": (
                    "Endocrinology and metabolism with clinical application. "
                    "Hypothalamic-pituitary-end-organ axes. Thyroid: hypothyroidism and Hashimoto's, "
                    "hyperthyroidism and Graves' disease, thyroid cancer. "
                    "Adrenal: Addison's disease, Cushing's syndrome, Conn's syndrome, "
                    "phaeochromocytoma. Diabetes mellitus: type 1 and 2, insulin physiology, "
                    "oral agents, DKA, HHS, long-term complications. "
                    "Metabolic syndrome and obesity. Calcium and bone metabolism: "
                    "hyperparathyroidism, osteoporosis, vitamin D deficiency."
                ),
                "description_tr": (
                    "Klinik uygulamalı endokrinoloji ve metabolizma. "
                    "Hipotalamo-hipofiz-hedef organ eksenleri. Tiroid hastalıkları. "
                    "Adrenal hastalıklar: Addison, Cushing, Conn, feokromositoma. "
                    "Diabetes mellitus: tip 1 ve 2, insülin fizyolojisi, oral ajanlar, DKA, HHS, "
                    "uzun dönem komplikasyonlar. Metabolik sendrom ve obezite. "
                    "Kalsiyum ve kemik metabolizması: hiperparatiroidizm, osteoporoz."
                ),
            },
            {
                "id": "Y3B4",
                "block_number": 4,
                "name_en": "Musculoskeletal, Dermatology & Reproductive",
                "name_tr": "Kas-İskelet, Dermatoloji ve Üreme Sistemi",
                "weeks": "21–26",
                "departments": ["Orthopedics and Traumatology", "Dermatology", "Obstetrics and Gynecology"],
                "topics": [
                    "osteoarthritis", "rheumatoid arthritis", "gout", "pseudogout",
                    "spondyloarthropathies", "ankylosing spondylitis", "psoriatic arthritis",
                    "SLE", "connective tissue diseases",
                    "bone diseases", "fractures", "osteoporosis", "bone tumours",
                    "soft tissue disorders", "back pain", "disc herniation",
                    "skin structure", "skin lesion terminology",
                    "eczema", "dermatitis", "psoriasis", "acne",
                    "skin infections", "cellulitis", "herpes", "tinea",
                    "melanoma", "basal cell carcinoma", "squamous cell carcinoma",
                    "female reproductive anatomy", "menstrual cycle",
                    "contraception", "infertility basics",
                    "gynaecological infections", "STIs",
                    "ovarian cancer", "cervical cancer", "endometrial cancer",
                    "male reproductive anatomy", "benign prostatic hyperplasia",
                ],
                "competencies": ["Medical Knowledge", "Patient Care"],
                "prerequisite_ids": ["Y1B3"],
                "description_en": (
                    "Integrated musculoskeletal, dermatological and reproductive medicine. "
                    "Musculoskeletal: osteoarthritis, rheumatoid arthritis, gout; "
                    "spondyloarthropathies; SLE and connective tissue diseases; fractures and "
                    "orthopaedic emergencies; back pain and disc disease. "
                    "Dermatology: skin structure and lesion terminology; eczema, psoriasis; "
                    "skin infections; melanoma and common skin cancers. "
                    "Reproductive: gynaecological anatomy, menstrual cycle, contraception; "
                    "common gynaecological conditions; gynaecological malignancies; "
                    "male reproductive disorders including BPH."
                ),
                "description_tr": (
                    "Entegre kas-iskelet, dermatoloji ve üreme tıbbı. "
                    "Kas-iskelet: osteoartrit, romatoid artrit, gut; spondilartropatiler; SLE; "
                    "kırıklar ve ortopedik aciller; bel ağrısı ve disk hastalığı. "
                    "Dermatoloji: deri yapısı ve lezyon terminolojisi; egzama, psoriasis; "
                    "deri enfeksiyonları; melanom ve yaygın deri kanserleri. "
                    "Üreme: jinekolojik anatomi, adet döngüsü, kontrasepsiyon; "
                    "jinekolojik maligniteler; BPH."
                ),
            },
            {
                "id": "Y3VI",
                "block_number": 5,
                "name_en": "Vertical Integration — Year 3",
                "name_tr": "Dikey Entegrasyon — 3. Yıl",
                "weeks": "1–26 (parallel)",
                "departments": ["General Surgery", "Medical Pharmacology"],
                "topics": [
                    "clinical skills III", "neurological examination",
                    "musculoskeletal examination", "skin examination",
                    "surgical principles", "wound healing", "antisepsis",
                    "pre-operative assessment", "anaesthesia basics",
                    "advanced pharmacology", "drug interactions",
                ],
                "competencies": ["Patient Care", "Medical Knowledge"],
                "prerequisite_ids": ["Y2VI"],
                "description_en": (
                    "Year 3 vertical integration strand. Clinical Skills III: neurological and "
                    "musculoskeletal examination; dermatological examination. "
                    "Surgery Principles: wound healing, antisepsis, pre-op assessment, "
                    "anaesthesia overview, common surgical conditions. "
                    "Advanced Pharmacology: drug interactions, special populations, "
                    "rational prescribing."
                ),
                "description_tr": (
                    "3. Yıl dikey entegrasyon bileşeni. Klinik Beceriler III: nörolojik ve "
                    "kas-iskelet muayenesi; dermatoljik muayene. "
                    "Cerrahi İlkeleri: yara iyileşmesi, asepsi, pre-op değerlendirme, anestezi. "
                    "İleri Farmakoloji: ilaç etkileşimleri, özel popülasyonlar."
                ),
            },
        ],
    },

    # YEAR 4
    {
        "year": 4,
        "name_en": "Year 4 — Clinical Rotations I",
        "name_tr": "4. Yıl — Klinik Rotasyonlar I",
        "description_en": "Supervised hospital rotations: internal medicine, surgery, paediatrics, OB/GYN, psychiatry, emergency.",
        "description_tr": "Denetimli hastane rotasyonları: iç hastalıkları, cerrahi, pediatri, kadın-doğum, psikiyatri, acil.",
        "blocks": [
            {
                "id": "Y4R1",
                "block_number": 1,
                "name_en": "Internal Medicine Rotation",
                "name_tr": "İç Hastalıkları Rotasyonu",
                "weeks": "8 weeks",
                "departments": ["Internal Medicine"],
                "topics": [
                    "inpatient medicine", "ward rounds", "clinical reasoning",
                    "history taking", "clinical examination", "differential diagnosis",
                    "common presentations: chest pain, dyspnoea, fever, abdominal pain",
                    "clinical investigations: bloods, imaging, ECG",
                    "therapeutic management", "discharge planning",
                    "medical documentation", "clinical handover",
                ],
                "competencies": ["Patient Care", "Medical Knowledge", "Communication", "Professionalism"],
                "prerequisite_ids": ["Y3B1", "Y3B2", "Y3B3"],
                "description_en": (
                    "Eight-week supervised rotation on the internal medicine ward at Koç University Hospital. "
                    "Students participate in ward rounds, clerking of admissions, and formulation of "
                    "management plans under consultant and registrar supervision. "
                    "Focus: clinical reasoning for common medical presentations, investigation "
                    "interpretation, and safe prescribing. Clinical logbook required."
                ),
                "description_tr": (
                    "Koç Üniversitesi Hastanesi'nde iç hastalıkları servisinde sekiz haftalık "
                    "denetimli rotasyon. Öğrenciler vizite, hasta kabul ve tedavi planı oluşturma "
                    "süreçlerine katılır. Odak: yaygın tıbbi prezentasyonlar için klinik muhakeme, "
                    "tetkik yorumlama ve güvenli ilaç reçetelemesi. Klinik logbook zorunludur."
                ),
            },
            {
                "id": "Y4R2",
                "block_number": 2,
                "name_en": "General Surgery Rotation",
                "name_tr": "Genel Cerrahi Rotasyonu",
                "weeks": "8 weeks",
                "departments": ["General Surgery"],
                "topics": [
                    "surgical clerking", "pre-operative assessment",
                    "operating theatre protocols", "scrubbing in",
                    "wound management", "surgical site infections",
                    "abdominal surgery", "appendicectomy", "cholecystectomy",
                    "hernia repair", "colorectal surgery",
                    "post-operative care", "complications",
                    "emergency surgery", "acute abdomen",
                ],
                "competencies": ["Patient Care", "Medical Knowledge", "Professionalism"],
                "prerequisite_ids": ["Y3VI"],
                "description_en": (
                    "Eight-week surgical rotation covering both elective and emergency general surgery. "
                    "Pre-operative clerking and assessment; theatre experience including scrubbing in "
                    "for common procedures (laparoscopic cholecystectomy, appendicectomy, hernia repair); "
                    "post-operative ward management; recognition and management of surgical complications. "
                    "Emergency surgery: acute abdomen, bowel obstruction, perforation."
                ),
                "description_tr": (
                    "Elektif ve acil genel cerrahi kapsayan sekiz haftalık cerrahi rotasyonu. "
                    "Pre-op hasta kabulü ve değerlendirme; yaygın prosedürler için ameliyathane deneyimi; "
                    "post-op servis yönetimi; cerrahi komplikasyonların tanınması ve yönetimi. "
                    "Acil cerrahi: akut karın, bağırsak tıkanması, perforasyon."
                ),
            },
            {
                "id": "Y4R3",
                "block_number": 3,
                "name_en": "Paediatrics Rotation",
                "name_tr": "Pediatri Rotasyonu",
                "weeks": "6 weeks",
                "departments": ["Pediatrics", "Child and Adolescent Mental Health and Diseases"],
                "topics": [
                    "child development", "developmental milestones",
                    "neonatal medicine", "neonatal jaundice", "neonatal sepsis",
                    "paediatric infections", "bronchiolitis", "croup", "febrile seizures",
                    "common childhood conditions", "asthma in children",
                    "paediatric examination", "paediatric prescribing",
                    "child safeguarding", "non-accidental injury",
                    "adolescent health",
                ],
                "competencies": ["Patient Care", "Medical Knowledge", "Communication"],
                "prerequisite_ids": ["Y2B3", "Y3B3"],
                "description_en": (
                    "Six-week paediatric rotation across inpatient ward and outpatient clinics. "
                    "Child development and growth monitoring. Neonatal medicine. "
                    "Common paediatric presentations: respiratory infections, febrile illnesses, "
                    "paediatric asthma, gastroenteritis. Paediatric examination technique and "
                    "age-adjusted normal values. Paediatric prescribing and fluid management. "
                    "Child safeguarding and recognition of non-accidental injury."
                ),
                "description_tr": (
                    "Yatan hasta servisi ve ayaktan poliklinik kapsayan altı haftalık pediatri rotasyonu. "
                    "Çocuk gelişimi ve büyüme takibi. Yenidoğan tıbbı. "
                    "Yaygın pediatrik prezentasyonlar: solunum yolu enfeksiyonları, febril hastalıklar, "
                    "çocukluk astımı, gastroenterit. Pediatrik muayene tekniği. "
                    "Pediatrik ilaç reçetelemesi ve sıvı yönetimi. Çocuk koruma."
                ),
            },
            {
                "id": "Y4R4",
                "block_number": 4,
                "name_en": "OB/GYN Rotation",
                "name_tr": "Kadın Hastalıkları ve Doğum Rotasyonu",
                "weeks": "6 weeks",
                "departments": ["Obstetrics and Gynecology"],
                "topics": [
                    "antenatal care", "normal labour", "operative delivery",
                    "obstetric emergencies", "pre-eclampsia", "postpartum haemorrhage",
                    "gynaecological examination", "speculum examination",
                    "menstrual disorders", "endometriosis",
                    "gynaecological oncology", "cervical screening",
                    "contraception clinics", "STI management",
                ],
                "competencies": ["Patient Care", "Medical Knowledge", "Communication"],
                "prerequisite_ids": ["Y3B4"],
                "description_en": (
                    "Six-week obstetrics and gynaecology rotation. "
                    "Obstetrics: antenatal assessment, labour ward experience including normal and "
                    "operative deliveries, obstetric emergencies (pre-eclampsia, PPH). "
                    "Gynaecology: outpatient clinic experience, gynaecological examination technique, "
                    "menstrual disorders, endometriosis, ovarian pathology, cervical screening programme."
                ),
                "description_tr": (
                    "Altı haftalık kadın hastalıkları ve doğum rotasyonu. "
                    "Obstetrik: antenatal değerlendirme, normal ve operatif doğum deneyimi, "
                    "obstetrik aciller. Jinekoloji: poliklinik deneyimi, jinekolojik muayene tekniği, "
                    "menstrüel bozukluklar, endometriozis, servikal tarama programı."
                ),
            },
            {
                "id": "Y4R5",
                "block_number": 5,
                "name_en": "Psychiatry & Emergency Medicine",
                "name_tr": "Psikiyatri ve Acil Tıp",
                "weeks": "8 weeks (4+4)",
                "departments": ["Psychiatry", "Emergency Medicine"],
                "topics": [
                    "psychiatric assessment", "MSE", "risk assessment",
                    "inpatient psychiatry", "depot medications",
                    "ECT", "community psychiatry",
                    "emergency triage", "ABCDE approach",
                    "resuscitation", "BLS ALS",
                    "trauma assessment", "ATLS",
                    "toxicology", "overdose management",
                    "emergency procedures",
                ],
                "competencies": ["Patient Care", "Medical Knowledge", "Professionalism"],
                "prerequisite_ids": ["Y3B1"],
                "description_en": (
                    "Four weeks psychiatry: inpatient and outpatient psychiatric assessment, "
                    "mental state examination, risk assessment, psychopharmacology in practice, "
                    "ECT, community mental health. "
                    "Four weeks emergency medicine: triage, ABCDE approach, resuscitation (BLS/ALS), "
                    "trauma (ATLS), common emergency presentations, toxicology and overdose."
                ),
                "description_tr": (
                    "Dört hafta psikiyatri: yatan hasta ve ayaktan psikiyatrik değerlendirme, "
                    "mental durum muayenesi, risk değerlendirmesi, psikofarmakoloji, EKT. "
                    "Dört hafta acil tıp: triaj, ABCDE yaklaşımı, resüsitasyon, travma, "
                    "yaygın acil prezentasyonlar, toksikoloji."
                ),
            },
        ],
    },

    # YEAR 5
    {
        "year": 5,
        "name_en": "Year 5 — Clinical Rotations II & Research",
        "name_tr": "5. Yıl — Klinik Rotasyonlar II ve Araştırma",
        "description_en": "Advanced clinical rotations: cardiology, neurology, radiology, infectious diseases, subspecialty electives and research thesis.",
        "description_tr": "İleri klinik rotasyonlar ve tez.",
        "blocks": [
            {
                "id": "Y5R1",
                "block_number": 1,
                "name_en": "Cardiology & Neurology",
                "name_tr": "Kardiyoloji ve Nöroloji",
                "weeks": "8 weeks (4+4)",
                "departments": ["Cardiology", "Neurology"],
                "topics": [
                    "echocardiography", "cardiac catheterisation", "PCI",
                    "device therapy", "pacemakers ICD",
                    "stroke unit", "thrombolysis", "thrombectomy",
                    "neurorehabilitation", "MS management",
                ],
                "competencies": ["Patient Care", "Medical Knowledge"],
                "prerequisite_ids": ["Y4R1"],
            },
            {
                "id": "Y5R2",
                "block_number": 2,
                "name_en": "Radiology & Infectious Diseases",
                "name_tr": "Radyoloji ve Enfeksiyon Hastalıkları",
                "weeks": "8 weeks (4+4)",
                "departments": ["Radiology", "Infectious Diseases and Clinical Microbiology"],
                "topics": [
                    "CT interpretation", "MRI principles", "ultrasound",
                    "interventional radiology",
                    "antimicrobial stewardship", "sepsis management",
                    "HIV", "TB", "tropical diseases",
                ],
                "competencies": ["Patient Care", "Medical Knowledge"],
                "prerequisite_ids": ["Y4R1"],
            },
            {
                "id": "Y5R3",
                "block_number": 3,
                "name_en": "Subspecialty Electives & Research Thesis",
                "name_tr": "Seçmeli Rotasyonlar ve Araştırma Tezi",
                "weeks": "16 weeks",
                "departments": ["Various"],
                "topics": [
                    "subspecialty clinical experience",
                    "research methodology", "thesis writing",
                    "statistical analysis", "academic presentation",
                ],
                "competencies": ["Scientific Inquiry", "Professionalism"],
                "prerequisite_ids": ["Y4R1", "Y4R2"],
            },
        ],
    },

    # YEAR 6
    {
        "year": 6,
        "name_en": "Year 6 — Internship",
        "name_tr": "6. Yıl — İntörnlük",
        "description_en": "Full-year supervised clinical internship across all major departments and thesis completion.",
        "description_tr": "Tüm ana bölümlerde tam yıl denetimli klinik intörnlük ve tez tamamlama.",
        "blocks": [
            {
                "id": "Y6I1",
                "block_number": 1,
                "name_en": "Clinical Internship Program",
                "name_tr": "Klinik İntörnlük Programı",
                "weeks": "48 weeks",
                "departments": [
                    "Internal Medicine", "General Surgery", "Pediatrics",
                    "Obstetrics and Gynecology", "Psychiatry", "Emergency Medicine",
                    "Neurology", "Cardiology", "Radiology",
                ],
                "topics": [
                    "independent clinical practice", "supervised patient management",
                    "on-call duties", "night shifts",
                    "procedural competencies", "clinical milestones",
                    "medical thesis completion", "oral thesis defence",
                    "final competency assessment", "graduation",
                ],
                "competencies": [
                    "Medical Knowledge", "Patient Care", "Communication",
                    "Professionalism", "System-Based Practice", "Scientific Inquiry",
                ],
                "prerequisite_ids": ["Y5R1", "Y5R2", "Y5R3"],
                "description_en": (
                    "Final year 48-week supervised clinical internship across all major departments. "
                    "Students function as sub-interns under close supervision, managing patients "
                    "independently with escalation pathways. On-call and night duties are included. "
                    "Completion of medical thesis and oral defence. "
                    "Final competency-based assessment covering all six domains: "
                    "medical knowledge, patient care, communication, professionalism, "
                    "systems-based practice, and scientific inquiry."
                ),
                "description_tr": (
                    "Son yıl 48 haftalık tüm ana bölümlerde denetimli klinik intörnlük. "
                    "Öğrenciler yakın denetim altında alt-asistan olarak hastaları bağımsız yönetir. "
                    "Nöbet ve gece vardiyaları dahildir. "
                    "Tıbbi tez tamamlama ve sözlü savunma. "
                    "Altı yetkinlik alanının tamamını kapsayan son yetkinlik bazlı değerlendirme."
                ),
            },
        ],
    },
]


#  Chunk Builder: converts curriculum into retrieval docs

def build_chunks(curriculum: list[dict]) -> list[dict]:
    """
    Convert the curriculum structure into flat text chunks
    suitable for FAISS and BM25 indexing.
    """
    chunks = []
    for year_data in curriculum:
        for block in year_data["blocks"]:
            # Main block chunk (EN)
            content_en = (
                f"Block {block['id']}: {block['name_en']} (Year {year_data['year']}, Weeks {block.get('weeks','')})\n"
                f"Departments: {', '.join(block.get('departments', []))}\n"
                f"Prerequisites: {', '.join(block.get('prerequisite_ids', [])) or 'None'}\n"
                f"Topics: {', '.join(block.get('topics', []))}\n"
                f"Description: {block.get('description_en', '')}"
            )
            chunks.append({
                "id": f"{block['id']}_en",
                "content": content_en,
                "source": block["id"],
                "source_type": "block",
                "metadata": {
                    "id": block["id"],
                    "name_en": block["name_en"],
                    "name_tr": block["name_tr"],
                    "year": year_data["year"],
                    "weeks": block.get("weeks", ""),
                    "departments": block.get("departments", []),
                    "language": "en",
                },
            })
            # Turkish block chunk
            content_tr = (
                f"Blok {block['id']}: {block['name_tr']} (Yıl {year_data['year']}, Haftalar {block.get('weeks','')})\n"
                f"Bölümler: {', '.join(block.get('departments', []))}\n"
                f"Ön koşullar: {', '.join(block.get('prerequisite_ids', [])) or 'Yok'}\n"
                f"Konular: {', '.join(block.get('topics', []))}\n"
                f"Açıklama: {block.get('description_tr', '')}"
            )
            chunks.append({
                "id": f"{block['id']}_tr",
                "content": content_tr,
                "source": block["id"],
                "source_type": "block",
                "metadata": {
                    "id": block["id"],
                    "name_en": block["name_en"],
                    "name_tr": block["name_tr"],
                    "year": year_data["year"],
                    "language": "tr",
                },
            })
            # Individual topic chunks for fine-grained retrieval
            details = {d["title"]: d for d in block.get("topic_details", [])}
            for ti, topic in enumerate(block.get("topics", [])):
                d = details.get(topic, {})
                extra = ""
                if d.get("kind"):
                    extra += f"\nSession type: {d['kind']}"
                if d.get("first_date"):
                    extra += f"\nFirst taught: {d['first_date']}"
                if d.get("objectives"):
                    extra += "\nLearning objectives: " + "; ".join(d["objectives"][:12])
                dept = (d.get("fields") or block.get("departments") or [""])[0]
                chunks.append({
                    "id": d.get("id") or f"{block['id']}_topic_{ti:03d}_{topic[:30].replace(' ', '_')}",
                    "content": (
                        f"Topic: {topic}\n"
                        f"Covered in: {block['name_en']} ({block['id']}) — Year {year_data['year']}\n"
                        f"Department: {dept}{extra}"
                    ),
                    "source": block["id"],
                    "source_type": "topic",
                    "metadata": {
                        "topic": topic,
                        "block_id": block["id"],
                        "name_en": block["name_en"],
                        "year": year_data["year"],
                        "language": "en",
                    },
                })
    return chunks
