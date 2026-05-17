from flask import Flask, render_template_string, request
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import io
import base64
import re
from collections import defaultdict

app = Flask(__name__)

sheet1_df = pd.read_excel("data.xlsx", sheet_name="Sheet1")
sheet2_df = pd.read_excel("data.xlsx", sheet_name="Sheet2")

# Load residency data
try:
    residency_24_df = pd.read_excel("24.xlsx")
    residency_25_df = pd.read_excel("25.xlsx")
except FileNotFoundError:
    residency_24_df = pd.DataFrame()
    residency_25_df = pd.DataFrame()

# ──────────────────────────────────────────────────────────────────
#  AI PREDICTION HELPERS
# ──────────────────────────────────────────────────────────────────

DEFAULT_HOSPITAL = 'المستشفى الرئيسي – الإسكندرية'

# ── Real hospitals (parentheses content → canonical hospital name) ──
HOSPITAL_MAP = {
    'الطلبة':                          'مستشفى الطلبة',
    'مستشفى الطلبة':                   'مستشفى الطلبة',
    'برج العرب':                       'برج العرب',
    'معهد بحوث':                       'معهد البحوث الطبية',
    'معهد البحوث':                     'معهد البحوث الطبية',
    'معهد البحوث الطبية':              'معهد البحوث الطبية',
    'معهد البحوث الطبية لأبحاث':       'معهد البحوث الطبية',
    'سموحة':                           'مستشفى سموحة',
    'مستشفى سموحة':                    'مستشفى سموحة',
    'المعهد العالي للصحة العامة':      'المعهد العالي للصحة العامة',
}

# ── 2024 "وحدة" units → canonical specialty (subspecialty encoded in name) ──
UNIT_TO_SPECIALTY = {
    'وحدة الغدد الصماء':                      'باطنة غدد',
    'وحدة الأمراض الروماتيزمية':               'باطنة روماتيزم',
    'وحدة الجهاز الهضمي':                     'باطنة جهاز هضمي',
    'وحدة أمراض الكبد والمرارة والبنكرياس':    'باطنة كبد',
    'وحدة السكر والميتابوليزم':                'باطنة سكر',
    'وحدة أمراض وزراعة الكلى':                'باطنة كلى',
    'وحدة أمراض الدم':                        'باطنة دم',
    'وحدة طب المسنين':                        'باطنة مسنين',
    'وحدة الجهاز الهضمي العلوي والكبد ب':     'جراحة جهاز هضمي',
    'وحدة الجهاز الهضمي العلوي والكبد':       'جراحة جهاز هضمي',
    'وحدة جراحة الأورام':                     'جراحة أورام',
    'وحدة جراحة الأوعية الدموية':             'جراحة أوعية',
    'وحدة جراحة الرأس والعنق':                'جراحة رأس وعنق',
    'وحدة جراحة الشرج والقولون':              'جراحة شرج وقولون',
}

# ── Parentheses that carry specialty info, NOT hospital ──
# value = override specialty (None = drop the parenthetical, keep base specialty)
NON_HOSPITAL_MAP = {
    'باثولوجي':                                    'باثولوجي',
    'وراثة':                                        'وراثة',
    'قسم طب الأطفال':                              None,   # ignore this label
    'ادارة المستشفيات':                             'ادارة مستشفيات',
    'الادارة والتخطيط والسياسة الصحية':            'ادارة صحية',
    'طب صناعات':                                    'طب صناعات',
    'صحة عامة':                                     'صحة عامة',
    'صحة الام والطفل':                              'صحة أم وطفل',
    'صحة المسنين':                                  'صحة مسنين',
}

# ── Canonical specialty names: map 2024 long names → 2025 short names ──
SPECIALTY_NORM = {
    # Cardiology
    'القلب والأوعية الدموية':                       'قلب وأوعية دموية',
    'أمراض القلب والأوعية الدموية':                'قلب وأوعية دموية',
    # Pediatrics
    'طب الأطفال':                                   'أطفال',
    # Pediatric surgery
    'جراحة الأطفال':                                'جراحة أطفال',
    # Pediatric ICU
    'العناية المركزة للأطفال بجراحة الأطفال':      'عناية جراحة أطفال',
    'العناية المركزة للأطفال بجراحة المخ والأعصاب':'عناية مخ وأعصاب',
    # Orthopedics
    'جراحة العظام والإصابات':                      'جراحة عظام',
    'جراحة العظام والاصابات':                      'جراحة عظام',
    # Cardiac surgery
    'جراحة القلب والصدر':                          'جراحة قلب وصدر',
    # General surgery
    'الجراحة العامة':                               'جراحة',
    'الجراحة التجريبية والاكلينيكية':              'جراحة',
    # Internal medicine
    'الباطنة العامة':                               'باطنة',
    'الباطنة التجريبية والاكلينيكية':              'باطنة',
    'الباطنه التجريبية والاكلينيكية':              'باطنة',
    'الباطنة':                                      'باطنة',
    # Blood diseases (without وحدة encoding)
    'أمراض الدم':                                   'باطنة دم',
    # OB/GYN
    'أمراض النساء والتوليد':                       'نسا وتوليد',
    # Dermatology
    'الأمراض الجلدية والتناسلية وأمراض الذكورة':   'جلدية',
    # Pulmonology
    'الأمراض الصدرية':                             'صدرية',
    # ENT
    'الأنف والأذن والحنجرة':                       'أنف وأذن وحنجرة',
    'الانف والاذن والحنجرة':                       'أنف وأذن وحنجرة',
    # Rheumatology / physical medicine
    'الروماتيزم والتأهيل والطب الطبيعي':           'طب طبيعي',
    # Anesthesia
    'التخدير والعناية المركزة الجراحية':           'تخدير وعناية',
    'التخدير وعلاج الألم':                         'تخدير',
    'التخدير وعلاج الالم':                         'تخدير',
    # Neurology / psychiatry
    'أمراض المخ والأعصاب والطب النفسي':            'نفسية وعصبية',
    # Neurosurgery
    'جراحة المخ والاعصاب':                         'جراحة مخ وأعصاب',
    # Radiology
    'الأشعة التشخيصية':                            'أشعة تشخيصية',
    'الاشعة التشخيصية':                            'أشعة تشخيصية',
    'الأشعة التشخيصية والتداخلية':                 'أشعة',
    'الاشعة التشخيصية والتداخلية':                 'أشعة',
    # Oncology
    'علاج الأورام والطب النووى':                   'علاج الأورام والطب النووي',
    'علاج ابحاث الأورام':                          'علاج الأورام والطب النووي',
    # Urology
    'جراحة المسالك البولية':                       'جراحة مسالك',
    'جراحة المسالك':                               'جراحة مسالك',
    # Plastic surgery
    'جراحة التجميل':                               'جراحة تجميل',
    # Forensic medicine
    'الطب الشرعي':                                 'طب شرعي',
    # Emergency
    'طب الطوارئ':                                  'طوارئ',
    'طب الطوارئ والاصابات':                        'طوارئ',
    # Community medicine / public health
    'طب المجتمع':                                  'طب مجتمع',
    # Pathology
    'الباثولوجيا':                                  'باثولوجي',
    'الباثولوجيا الإكلينيكية':                     'كلينيكال باثولوجي',
    'الباثولوجيا الاكلينيكية':                     'كلينيكال باثولوجي',
    # Basic sciences
    'التشريح':                                      'اناتومي',
    'الفارماكولوجي':                                'فارما',
    'الفسيولوجيا':                                  'فسيولوجي',
    'الميكروبيولوجيا':                              'ميكروبيولوجي',
    'الاحياء الدقيقة':                              'ميكروبيولوجي',
    'الهستولوجيا':                                  'هستولوجي',
    'الكيمياء الحيوية':                             'بايوكيمستري',
    'الطفيليات':                                    'باراسيتولوجي',
    'الوراثة الانسانية':                            'وراثة',
    'المعلوماتية الحيوية الطبية والاحصاء الطبي':    'بيوانفورماتيكس',
    'الاحصاءات الحيوية':                            'احصاء حيوي',
    'الوبائيات':                                    'صحة عامة',
    'التغذية':                                      'تغذية',
    # Other
    'التعليم الطبي':                                'تعليم طبي',
    'الادارة الصحية والعلوم السلوكية':              'ادارة مستشفيات',
    'صحة الاسرة':                                   'صحة الاسرة',
}


def _normalize_specialty(raw: str) -> str:
    """Apply canonical name mapping to a specialty string."""
    return SPECIALTY_NORM.get(raw.strip(), raw.strip())


def get_canonical_entry(raw_name: str):
    """
    Convert ANY raw residency name (2024 or 2025) →  (canonical_specialty, canonical_hospital).

    Handles three 2024 patterns that mislead the naive split:
      1. "الباطنة العامة (وحدة الغدد الصماء)"  → ('باطنة غدد', DEFAULT_HOSPITAL)
      2. "الباثولوجيا (وراثة)"                  → ('وراثة',     DEFAULT_HOSPITAL)
      3. "طب المجتمع (صحة عامة)"               → ('صحة عامة',  DEFAULT_HOSPITAL)
    """
    raw = str(raw_name).strip()

    # ── Step 1: detect "وحدة" inside parentheses ──
    unit_m = re.search(r'\(([^)]*وحدة[^)]*)\)', raw)
    if unit_m:
        unit_text = unit_m.group(1).strip()
        for key, canonical in UNIT_TO_SPECIALTY.items():
            if key in unit_text:
                return canonical, DEFAULT_HOSPITAL
        # Unknown unit — strip parenthetical, normalize base
        base = re.sub(r'\s*\([^)]+\)', '', raw).strip()
        return _normalize_specialty(base), DEFAULT_HOSPITAL

    # ── Step 2: extract parenthetical ──
    paren_m = re.match(r'^(.*?)\s*\(([^)]+)\)\s*$', raw)
    if paren_m:
        base_part  = paren_m.group(1).strip()
        paren_part = paren_m.group(2).strip()

        # Is the parenthetical a non-hospital specialty descriptor?
        if paren_part in NON_HOSPITAL_MAP:
            override = NON_HOSPITAL_MAP[paren_part]
            if override is None:
                # Drop the parenthetical label entirely
                return _normalize_specialty(base_part), DEFAULT_HOSPITAL
            else:
                return override, DEFAULT_HOSPITAL

        # It's a real hospital
        hospital = HOSPITAL_MAP.get(paren_part, paren_part)
        return _normalize_specialty(base_part), hospital

    # ── Step 3: no parentheses ──
    return _normalize_specialty(raw), DEFAULT_HOSPITAL


def _build_records(df24, df25):
    """Flatten both dataframes into a list of dicts with numeric rank."""
    records = []
    for year, df in [('2024', df24), ('2025', df25)]:
        if df is None or df.empty:
            continue
        for _, row in df.iterrows():
            try:
                rank_num = int(str(row.get('RANK', '')).strip())
            except (ValueError, TypeError):
                continue
            residency = str(row.get('RESIDENCY', '')).strip()
            if not residency or residency.lower() == 'nan':
                continue
            status = str(row.get('STATUS', '')).strip()
            specialty, hospital = get_canonical_entry(residency)
            records.append({
                'year':     year,
                'rank':     rank_num,
                'specialty': specialty,
                'hospital':  hospital,
                'is_post':   status == 'بوست',
                'status':    status,
            })
    return records


def _calc_probability(student_rank, min_rank, max_rank):
    """
    Sigmoid-inspired probability that a student gets a residency.
    95 % if at or above min_rank → 30 % at max_rank → 5 % beyond 1.3×max.
    """
    if max_rank == 0:
        return 5
    if student_rank <= min_rank:
        return 95
    if student_rank > max_rank * 1.3:
        return 3
    if student_rank > max_rank:
        excess  = student_rank - max_rank
        buffer  = max_rank * 0.3
        return max(4, int(30 * (1 - excess / buffer)))
    span = max_rank - min_rank
    if span == 0:
        return 90
    pos = student_rank - min_rank
    return max(30, int(95 - 65 * pos / span))


def get_residency_predictions(student_rank: int, df24, df25):
    """
    Return (post_list, nopost_list) — each sorted by probability desc.
    Probabilities are calculated SEPARATELY per status type so a specialty
    can have a different % for post vs no-post.
    Entries with لم يحضر / ويتنج are ignored.
    """
    records = _build_records(df24, df25)
    valid   = [r for r in records if r['status'] in ('بوست', 'بدون بوست')]

    groups = defaultdict(list)
    for r in valid:
        groups[(r['specialty'], r['hospital'], r['is_post'])].append(r)

    post_list, nopost_list = [], []
    for (specialty, hospital, is_post), grp in groups.items():
        ranks    = [r['rank'] for r in grp]
        min_rank = min(ranks)
        max_rank = max(ranks)
        years    = sorted(set(r['year'] for r in grp))
        prob     = _calc_probability(student_rank, min_rank, max_rank)

        entry = {
            'specialty':   specialty,
            'hospital':    hospital,
            'is_post':     is_post,
            'probability': prob,
            'min_rank':    min_rank,
            'max_rank':    max_rank,
            'years':       years,
            'sample_size': len(grp),
        }
        (post_list if is_post else nopost_list).append(entry)

    post_list.sort(key=lambda x: -x['probability'])
    nopost_list.sort(key=lambda x: -x['probability'])
    return post_list, nopost_list


# ──────────────────────────────────────────────────────────────────
#  TEMPLATES
# ──────────────────────────────────────────────────────────────────

html_template = """ 
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>AFM 26 RESULTS</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logoTB.png') }}">
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background-color: #f0f4f8;
            text-align: center;
            position: relative;
        }
        body::before {
            content: "";
            background-image: url('https://i.ibb.co/zHRhsP6j');
            background-size: cover;
            background-position: center;
            opacity: 0.1;
            top: 0; left: 0; bottom: 0; right: 0;
            position: fixed;
            z-index: -1;
        }
        .container {
            margin: 60px auto;
            width: 70%;
            background-color: rgba(255, 255, 255, 0.9);
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
        }
        .header { display: flex; align-items: center; justify-content: center; gap: 20px; margin-bottom: 30px; direction: ltr; }
        .header img { height: 70px; width: auto; opacity: 0.85; }
        .header-text { text-align: left; direction: ltr; }
        .header-text h1 { font-size: 36px; margin: 0; font-weight: 900; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .header-text h1 a { text-decoration: none; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .header-text p { font-size: 18px; margin: 5px 0 0 0; font-style: italic; font-weight: bold; background: linear-gradient(45deg, #ff6b6b, #4ecdc4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .header-text p a { text-decoration: none; font-style: italic; font-weight: bold; background: linear-gradient(45deg, #ff6b6b, #4ecdc4); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
        .nav-buttons { display: flex; justify-content: center; gap: 20px; margin: 30px 0; flex-wrap: wrap; }
        .nav-btn { padding: 15px 30px; font-size: 18px; font-weight: bold; border: none; border-radius: 25px; cursor: pointer; transition: all 0.3s ease; text-decoration: none; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .nav-btn.search  { background: linear-gradient(45deg, #4285f4, #34a853); }
        .nav-btn.distance{ background: linear-gradient(45deg, #ff6b6b, #4ecdc4); }
        .nav-btn.need    { background: linear-gradient(45deg, #9c27b0, #e91e63); }
        .nav-btn.residency{ background: linear-gradient(45deg, #f39c12, #e74c3c); }
        .nav-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
        .nav-btn.active { background: linear-gradient(45deg, #333, #555); }
        table { border-collapse: collapse; margin: auto; width: 100%; font-size: 18px; direction: rtl; background-color: #fff; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: center; }
        th { width: 40%; }
        td { width: 60%; font-weight: bold; }
        .title { font-weight: bold; font-size: 20px; background-color: #b3e5fc; color: #000; }
        .footer { background-color: #a0d080; font-style: italic; }
        .first-year  { background-color: #e0f7fa; }
        .second-year { background-color: #fff3e0; }
        .third-year  { background-color: #ede7f6; }
        .fourth-year { background-color: #d0e0ff; }
        .totals { background-color: #d0f8ce; }
        .rank   { background-color: #ffe0f0; }
        form { margin: 0 auto; display: flex; flex-direction: column; align-items: center; }
        label.title { font-size: 36px; font-weight: 800; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 25px; text-transform: uppercase; }
        .search-container { position: relative; margin: 20px 0; }
        input[type="text"], input[type="number"] { font-size: 24px; padding: 15px 25px; width: 400px; border: 2px solid #ddd; border-radius: 25px; transition: all 0.3s ease; outline: none; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        input[type="text"]:focus, input[type="number"]:focus { border-color: #4285f4; box-shadow: 0 0 15px rgba(66,133,244,0.3); transform: scale(1.02); }
        input[type="submit"] { font-size: 20px; padding: 12px 30px; margin-top: 15px; border-radius: 25px; background: linear-gradient(45deg, #4285f4, #34a853); color: white; border: none; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(66,133,244,0.3); }
        input[type="submit"]:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(66,133,244,0.4); }
        p { font-size: 22px; color: red; }
        .distance-result { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 20px; margin: 30px 0; box-shadow: 0 8px 25px rgba(0,0,0,0.3); }
        .distance-result h2 { font-size: 32px; margin-bottom: 20px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .progress-arrow-container { display: flex; align-items: center; justify-content: center; margin: 30px 0; position: relative; direction: ltr; }
        .progress-circle { width: 140px; height: 140px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; font-weight: bold; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); position: relative; z-index: 2; }
        .current-circle { background: linear-gradient(135deg, #ff6b6b, #ee5a52); box-shadow: 0 8px 20px rgba(255,107,107,0.4); }
        .target-circle  { background: linear-gradient(135deg, #4ecdc4, #44a08d); box-shadow: 0 8px 20px rgba(78,205,196,0.4); }
        .circle-label   { font-size: 16px; margin-bottom: 5px; opacity: 0.9; }
        .circle-value   { font-size: 26px; font-weight: 900; }
        .progress-arrow { flex: 0 0 200px; height: 12px; background: linear-gradient(90deg, #ff6b6b, #4ecdc4); margin: 0 25px; border-radius: 6px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .progress-arrow::after { content: ''; position: absolute; right: -18px; top: 50%; transform: translateY(-50%); width: 0; height: 0; border-left: 22px solid #4ecdc4; border-top: 20px solid transparent; border-bottom: 20px solid transparent; filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.3)); }
        .progress-difference { position: absolute; top: -50px; left: 50%; transform: translateX(-50%); background: rgba(255,255,255,0.95); color: #333; padding: 12px 20px; border-radius: 25px; font-size: 18px; font-weight: bold; box-shadow: 0 4px 15px rgba(0,0,0,0.2); z-index: 3; white-space: nowrap; min-width: 120px; text-align: center; }
        .progress-difference.positive { background: linear-gradient(135deg, #4CAF50, #45a049); color: white; }
        .progress-difference.negative { background: linear-gradient(135deg, #f44336, #e53935); color: white; }
        .progress-difference.neutral  { background: linear-gradient(135deg, #2196F3, #1976D2); color: white; }
        .motivational-message { background: linear-gradient(45deg, #ff6b6b, #4ecdc4); color: white; padding: 25px; border-radius: 15px; margin: 20px 0; font-size: 28px; font-weight: bold; text-shadow: 1px 1px 2px rgba(0,0,0,0.3); line-height: 1.4; }
        .motivational-message .highlight-number { font-size: 36px; text-decoration: underline; font-weight: 900; }
        .chart-title { font-size: 26px; font-weight: bold; color: white; margin: 30px 0 20px 0; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .percentile-box { background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4); background-size: 400% 400%; animation: gradientShift 3s ease infinite; color: white; font-size: 22px; font-weight: bold; padding: 20px; margin: 20px auto; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.3); text-shadow: 2px 2px 4px rgba(0,0,0,0.5); border: 3px solid white; max-width: 500px; position: relative; overflow: hidden; }
        @keyframes gradientShift { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
        .dual-input { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; justify-content: center; direction: ltr; }
        .dual-input input { width: 180px; }
        .dual-input label { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 5px; display: block; }
    </style>
    <script>
      window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
    </script>
    <script defer src="/_vercel/insights/script.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://i.postimg.cc/0rHzBdbx/8.jpg" alt="Logo">
            <div class="header-text">
                <h1><a href="/">AFM 26 Results &amp; Analysis</a></h1>
                <p><a href="https://t.me/Abdo_Hamdi6" target="_blank">By : Abdo Hamdy Aly</a></p>
            </div>
        </div>

        <div class="nav-buttons">
            <a href="/?mode=search"   class="nav-btn search   {{ 'active' if mode == 'search' or not mode else '' }}">🔍 Student Search</a>
            <a href="/?mode=distance" class="nav-btn distance {{ 'active' if mode == 'distance' else '' }}">📏 How Far I am</a>
            <a href="/?mode=need"     class="nav-btn need     {{ 'active' if mode == 'need' else '' }}">🎯 How Much I Need</a>
            <a href="/residency?year=2024" class="nav-btn residency">🏥 Residency Matching</a>
        </div>

        {% if mode == 'need' %}
        <form method="POST" action="/?mode=need">
            <label class="title">HOW MUCH I NEED</label><br>
            <div class="search-container">
                <div class="dual-input">
                    <div><label>Student ID</label><input type="text"   name="student_id"         placeholder="Enter your ID"  required></div>
                    <div><label>Target Total %</label><input type="number" name="target_percentage" step="0.01" min="0" max="100" placeholder="Target %" required></div>
                </div>
                <br><input type="submit" value="🧮 Calculate Required">
            </div>
        </form>

        {% if need_result %}
        <div class="distance-result">
            <h2>🎯 Required 5th Year Analysis</h2>
            <h3 style="font-size:30px;margin:15px 0;color:#ffeb3b;text-shadow:2px 2px 4px rgba(0,0,0,0.5);">{{ need_result['student_name'] }}</h3>
            <div class="progress-arrow-container">
                <div class="progress-circle current-circle">
                    <div class="circle-label">Current</div>
                    <div class="circle-value">{{ need_result['current_percentage'] }}%</div>
                </div>
                <div class="progress-arrow">
                    <div class="progress-difference {% if need_result['required_5th_year_percentage'] > 0 and need_result['required_5th_year_percentage'] <= 100 %}positive{% elif need_result['required_5th_year_percentage'] > 100 %}negative{% else %}neutral{% endif %}">
                        {% if need_result['required_5th_year_percentage'] > 100 %}Need &gt;100%
                        {% elif need_result['required_5th_year_percentage'] < 0 %}Target Achieved!
                        {% else %}Need {{ need_result['required_5th_year_percentage'] }}%{% endif %}
                    </div>
                </div>
                <div class="progress-circle target-circle">
                    <div class="circle-label">Target</div>
                    <div class="circle-value">{{ need_result['target_percentage'] }}%</div>
                </div>
            </div>
            {% if need_result['required_5th_year_percentage'] < 60 %}
                <div class="motivational-message" style="background:linear-gradient(45deg,#f44336,#ff5722);">
                    ❌ Target requires <span class="highlight-number">{{ need_result['required_5th_year_score'] }}</span> marks (<span class="highlight-number">{{ need_result['required_5th_year_percentage'] }}%</span>) in 5th year — below 60%!<br><br>This is impossible! Minimum passing grade is 60%. 🎯
                </div>
            {% elif need_result['required_5th_year_percentage'] <= 100 %}
                <div class="motivational-message">
                    🎯 You need <span class="highlight-number">{{ need_result['required_5th_year_score'] }}</span> / 1245 (<span class="highlight-number">{{ need_result['required_5th_year_percentage'] }}%</span>) in 5th year to reach {{ need_result['target_percentage'] }}%!<br><br>
                    {% if need_result['required_5th_year_percentage'] <= 70 %}Easy target! 💪{% elif need_result['required_5th_year_percentage'] <= 80 %}Good target! 📚{% elif need_result['required_5th_year_percentage'] <= 90 %}Challenging but doable! 🔥{% else %}Very challenging — give your best! 🚀{% endif %}
                </div>
            {% elif need_result['required_5th_year_percentage'] > 100 %}
                <div class="motivational-message" style="background:linear-gradient(45deg,#f44336,#ff5722);">
                    ⚠️ Target requires <span class="highlight-number">{{ need_result['required_5th_year_score'] }}</span> marks — above 100%! Consider a more realistic target. 🎯
                </div>
            {% else %}
                <div class="motivational-message" style="background:linear-gradient(45deg,#4CAF50,#45a049);">
                    🎉 You've already exceeded your target of {{ need_result['target_percentage'] }}%! Set a higher goal! 🏆
                </div>
            {% endif %}
        </div>
        {% elif need_searched %}
            <p>❌ Student not found or invalid target percentage</p>
        {% endif %}

        {% elif mode == 'distance' %}
        <form method="POST" action="/?mode=distance">
            <label class="title">HOW FAR I AM</label><br>
            <div class="search-container">
                <div class="dual-input">
                    <div><label>Student ID</label><input type="text"   name="student_id"   placeholder="Enter your ID" required></div>
                    <div><label>Target Rank</label><input type="number" name="target_rank" min="1" placeholder="Target rank" required></div>
                </div>
                <br><input type="submit" value="🎯 Calculate Distance">
            </div>
        </form>

        {% if distance_result %}
        <div class="distance-result">
            <h2>📊 Distance Analysis</h2>
            <h3 style="font-size:30px;margin:15px 0;color:#ffeb3b;text-shadow:2px 2px 4px rgba(0,0,0,0.5);">{{ distance_result['student_name'] }}</h3>
            <div class="progress-arrow-container">
                <div class="progress-circle current-circle">
                    <div class="circle-label">Current</div>
                    <div class="circle-value">#{{ distance_result['current_rank'] }}</div>
                </div>
                <div class="progress-arrow">
                    <div class="progress-difference {% if distance_result['points_needed'] > 0 %}positive{% elif distance_result['points_needed'] == 0 %}neutral{% else %}negative{% endif %}">
                        {% if distance_result['points_needed'] > 0 %}{{ distance_result['points_needed'] }} Marks Behind
                        {% elif distance_result['points_needed'] == 0 %}At Target!
                        {% else %}{{ distance_result['points_needed']|abs }} Marks Ahead{% endif %}
                    </div>
                </div>
                <div class="progress-circle target-circle">
                    <div class="circle-label">Target</div>
                    <div class="circle-value">#{{ distance_result['target_rank'] }}</div>
                </div>
            </div>
            {% if distance_result['points_needed'] > 0 %}
                <div class="motivational-message">
                    📏 Distance to rank #{{ distance_result['target_rank'] }}: <span class="highlight-number">{{ distance_result['points_needed'] }}</span> marks. Keep pushing! 💪
                </div>
            {% elif distance_result['points_needed'] == 0 %}
                <div class="motivational-message" style="background:linear-gradient(45deg,#4CAF50,#45a049);">🎉 Exactly at rank #{{ distance_result['target_rank'] }}! Perfect! 🏆</div>
            {% else %}
                <div class="motivational-message" style="background:linear-gradient(45deg,#4CAF50,#45a049);">
                    🌟 You're ahead by <span class="highlight-number">{{ distance_result['points_needed']|abs }}</span> marks! Keep it up! 🔥
                </div>
            {% endif %}
        </div>
        {% elif distance_searched %}
            <p>❌ Student not found or invalid target rank</p>
        {% endif %}

        {% else %}
        <form method="POST" action="/?mode=search">
            <label class="title">ENTER ID</label><br>
            <div class="search-container">
                <input type="text" name="student_id" required>
                <br><input type="submit" value="🔍 Search">
            </div>
        </form>

        {% if result %}
        <table>
            <tr><td colspan="2" class="title">👨‍🎓 اسم الطالب : {{ result['NAME'] }}</td></tr>
            <tr><th class="title">🔢 MARK</th><th class="title">📚 SUBJECT</th></tr>
            {% for key, value in result.items() %}
                {% if key != 'ID' and key != 'NAME' %}
                    {% set key_upper = key.upper().strip() %}
                    {% if key_upper in ['FIRST YEAR','LONG FIRST YEAR','RESEARCH STEP I','COMMUNICATION STEP I','PROFESSIONALISM STEP I'] %}{% set css_class = 'first-year' %}
                    {% elif key_upper in ['SECOND YEAR','LONG SECOND YEAR','RESEARCH STEP II','COMMUNICATION STEP II','PROFESSIONALISM STEP II'] %}{% set css_class = 'second-year' %}
                    {% elif key_upper in ['THIRD YEAR','LONG THIRD YEAR','RESEARCH STEP III','COMMUNICATION STEP III','PROFESSIONALISM STEP III'] %}{% set css_class = 'third-year' %}
                    {% elif key_upper in ['FOURTH YEAR','LONG FOURTH YEAR','RESEARCH STEP IIII','COMMUNICATION STEP IIII','PROFESSIONALISM STEP IIII'] %}{% set css_class = 'fourth-year' %}
                    {% elif key_upper in ['TOTAL','TOTAL RANK','%','PERCENTAGE'] %}{% set css_class = 'totals' %}
                    {% elif 'RANK' in key_upper %}{% set css_class = 'rank' %}
                    {% else %}{% set css_class = '' %}{% endif %}
                    <tr class="{{ css_class }}"><td>{{ value }}</td><td>{{ key }}</td></tr>
                {% endif %}
            {% endfor %}
            <tr class="footer"><td colspan="2">💻 Designed and Coded By : Abdo Hamdy Aly</td></tr>
            <tr>
                <td colspan="2" style="text-align:center;font-size:18px;padding:15px;">
                    <a href="https://t.me/Abdo_Hamdi6" target="_blank" style="text-decoration:none;color:black;">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg" alt="Telegram" style="width:24px;vertical-align:middle;margin-left:8px;">
                        📱 @Abdo_Hamdi6
                    </a>
                </td>
            </tr>
        </table>

        {% if plot_url %}
            <div class="chart-title">📈 Student Score Distribution</div>
            <img src="data:image/png;base64,{{ plot_url }}">
            {% if percentile %}
                <div class="percentile-box">🎯 YOU ARE IN THE {{ percentile }}th PERCENTILE! 🏆</div>
            {% endif %}
        {% endif %}
        {% if rank_progress_url %}
            <div class="chart-title">📊 Cumulative Rank Progress</div>
            <img src="data:image/png;base64,{{ rank_progress_url }}">
        {% endif %}

        {% elif searched %}
            <p>❌ Student not found</p>
        {% endif %}
        {% endif %}

        <div style="margin-top:40px;padding:20px 10px;border-radius:12px;background:linear-gradient(to right,black,white,green,red);color:white;font-size:24px;font-weight:bold;text-shadow:1px 1px 2px black;">
            🇵🇸 FREE PALESTINE 🇵🇸
        </div>
    </div>
</body>
</html>
"""

# ──────────────────────────────────────────────────────────────────
#  RESIDENCY LIST TEMPLATE (2024 / 2025 table view)
# ──────────────────────────────────────────────────────────────────
residency_template = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Residency Matching</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logoTB.png') }}">
    <style>
        body { font-family:'Arial',sans-serif; background-color:#f0f4f8; text-align:center; position:relative; }
        body::before { content:""; background-image:url('https://i.ibb.co/zHRhsP6j'); background-size:cover; background-position:center; opacity:0.1; top:0;left:0;bottom:0;right:0; position:fixed; z-index:-1; }
        .container { margin:60px auto; width:90%; max-width:1400px; background-color:rgba(255,255,255,0.9); padding:20px 30px; border-radius:10px; box-shadow:0 0 15px rgba(0,0,0,0.1); }
        .header { display:flex; align-items:center; justify-content:center; gap:20px; margin-bottom:30px; direction:ltr; }
        .header img { height:70px; width:auto; opacity:0.85; }
        .header-text { text-align:left; direction:ltr; }
        .header-text h1 { font-size:36px; margin:0; font-weight:900; background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .header-text h1 a { text-decoration:none; background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .header-text p { font-size:18px; margin:5px 0 0 0; font-style:italic; font-weight:bold; background:linear-gradient(45deg,#ff6b6b,#4ecdc4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .header-text p a { text-decoration:none; font-style:italic; font-weight:bold; background:linear-gradient(45deg,#ff6b6b,#4ecdc4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .nav-buttons { display:flex; justify-content:center; gap:15px; margin:30px 0; flex-wrap:wrap; }
        .nav-btn { padding:13px 25px; font-size:16px; font-weight:bold; border:none; border-radius:25px; cursor:pointer; transition:all 0.3s ease; text-decoration:none; color:white; box-shadow:0 4px 15px rgba(0,0,0,0.2); }
        .nav-btn.home      { background:linear-gradient(45deg,#667eea,#764ba2); }
        .nav-btn.year-2024 { background:linear-gradient(45deg,#ff6b6b,#ee5a52); }
        .nav-btn.year-2025 { background:linear-gradient(45deg,#4ecdc4,#44a08d); }
        .nav-btn.ai-predict{ background:linear-gradient(45deg,#f39c12,#8e44ad); }
        .nav-btn:hover { transform:translateY(-3px); box-shadow:0 6px 20px rgba(0,0,0,0.3); }
        .nav-btn.active { background:linear-gradient(45deg,#333,#555); }
        .page-title { font-size:36px; font-weight:800; background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin:30px 0; text-transform:uppercase; }
        .stats-container { display:flex; justify-content:center; gap:30px; margin:30px 0; flex-wrap:wrap; }
        .stat-box { background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; padding:20px 40px; border-radius:15px; box-shadow:0 4px 15px rgba(0,0,0,0.2); }
        .stat-number { font-size:36px; font-weight:bold; margin:10px 0; }
        .stat-label  { font-size:16px; opacity:0.9; }
        .table-container { overflow-x:auto; margin:30px 0; }
        table { border-collapse:collapse; margin:0 auto; width:100%; font-size:16px; direction:rtl; background-color:#fff; box-shadow:0 4px 15px rgba(0,0,0,0.1); border-radius:10px; overflow:hidden; }
        thead { position:sticky; top:0; z-index:10; }
        th { background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; font-weight:bold; font-size:18px; padding:15px 10px; text-align:center; border:1px solid rgba(255,255,255,0.2); }
        td { padding:12px 10px; text-align:center; border:1px solid #ddd; }
        tr:nth-child(even) { background-color:#f9f9f9; }
        tr:hover { background-color:#e3f2fd; transition:background-color 0.3s ease; }
        .boast-yes { background-color:#c8e6c9 !important; font-weight:bold; }
        .boast-yes:hover { background-color:#a5d6a7 !important; }
        .boast-no  { background-color:#ffe0b2 !important; }
        .boast-no:hover  { background-color:#ffcc80 !important; }
        .rank-col { font-weight:bold; color:#667eea; }
        p.error { font-size:22px; color:#f44336; font-weight:bold; margin:30px 0; }
        .search-box { margin:20px 0; padding:15px; background:rgba(255,255,255,0.5); border-radius:10px; }
        .search-box input { font-size:18px; padding:10px 20px; width:300px; border:2px solid #ddd; border-radius:25px; outline:none; transition:all 0.3s ease; }
        .search-box input:focus { border-color:#667eea; box-shadow:0 0 10px rgba(102,126,234,0.3); }
        .free-palestine { margin-top:40px; padding:20px 10px; border-radius:12px; background:linear-gradient(to right,black,white,green,red); color:white; font-size:24px; font-weight:bold; text-shadow:1px 1px 2px black; }
    </style>
    <script>
        function filterTable() {
            const input  = document.getElementById('searchInput');
            const filter = input.value.toUpperCase();
            const table  = document.getElementById('residencyTable');
            const tr     = table.getElementsByTagName('tr');
            for (let i = 1; i < tr.length; i++) {
                let found = false;
                const td = tr[i].getElementsByTagName('td');
                for (let j = 0; j < td.length; j++) {
                    if (td[j] && (td[j].textContent || td[j].innerText).toUpperCase().indexOf(filter) > -1) { found = true; break; }
                }
                tr[i].style.display = found ? '' : 'none';
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="https://i.postimg.cc/0rHzBdbx/8.jpg" alt="Logo">
            <div class="header-text">
                <h1><a href="/">AFM 26 Results &amp; Analysis</a></h1>
                <p><a href="https://t.me/Abdo_Hamdi6" target="_blank">By : Abdo Hamdy Aly</a></p>
            </div>
        </div>

        <div class="nav-buttons">
            <a href="/"                    class="nav-btn home">🏠 Home</a>
            <a href="/residency?year=2024" class="nav-btn year-2024 {{ 'active' if year == '2024' else '' }}">🏥 2024 Residencies</a>
            <a href="/residency?year=2025" class="nav-btn year-2025 {{ 'active' if year == '2025' else '' }}">🏥 2025 Residencies</a>
            <a href="/residency/predict"   class="nav-btn ai-predict">🤖 AI Prediction</a>
        </div>

        <div class="page-title">🩺 RESIDENCY MATCHING {{ year }}</div>

        {% if df_empty %}
            <p class="error">⚠️ No data available for {{ year }}</p>
        {% else %}
            <div class="stats-container">
                <div class="stat-box"><div class="stat-label">Total Students</div><div class="stat-number">{{ results|length }}</div></div>
                <div class="stat-box" style="background:linear-gradient(135deg,#4ecdc4,#44a08d);"><div class="stat-label">With Post</div><div class="stat-number">{{ boast_count }}</div></div>
                <div class="stat-box" style="background:linear-gradient(135deg,#ff6b6b,#ee5a52);"><div class="stat-label">Without Post</div><div class="stat-number">{{ no_boast_count }}</div></div>
            </div>

            <div class="search-box">
                <input type="text" id="searchInput" onkeyup="filterTable()" placeholder="🔍 Search by Rank, Residency...">
            </div>

            <div class="table-container">
                <table id="residencyTable">
                    <thead>
                        <tr><th>RANK</th><th>RESIDENCY</th><th>STATUS</th></tr>
                    </thead>
                    <tbody>
                        {% for row in results %}
                        {% set status_val = row.get('STATUS','')|string|trim %}
                        <tr class="{% if status_val == 'بوست' %}boast-yes{% else %}boast-no{% endif %}">
                            <td class="rank-col">{{ row.get('RANK','-') }}</td>
                            <td>{{ row.get('RESIDENCY','-') }}</td>
                            <td>{% if status_val == 'بوست' %}✅ {{ row['STATUS'] }}{% else %}{{ row.get('STATUS','-') }}{% endif %}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% endif %}

        <div class="free-palestine">🇵🇸 FREE PALESTINE 🇵🇸</div>
    </div>
</body>
</html>
"""

# ──────────────────────────────────────────────────────────────────
#  AI PREDICTION TEMPLATE
# ──────────────────────────────────────────────────────────────────
ai_predict_template = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AI Residency Prediction</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logoTB.png') }}">
    <style>
        :root {
            --primary: #667eea; --secondary: #764ba2;
            --green: #27ae60;   --orange: #e67e22;
            --bg: #f0f4f8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background: var(--bg); min-height: 100vh; }
        body::before { content:""; background-image:url('https://i.ibb.co/zHRhsP6j'); background-size:cover; background-position:center; opacity:.07; top:0;left:0;bottom:0;right:0; position:fixed; z-index:-1; }
        .container { max-width:1200px; margin:0 auto; padding:30px 20px; }

        /* HEADER */
        .header { display:flex; align-items:center; justify-content:center; gap:20px; margin-bottom:28px; }
        .header img { height:65px; opacity:.85; }
        .header-text h1 { font-size:30px; font-weight:900; background:linear-gradient(135deg,var(--primary),var(--secondary)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .header-text p { font-size:15px; font-style:italic; font-weight:bold; background:linear-gradient(45deg,#ff6b6b,#4ecdc4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .header-text a { text-decoration:none; }

        /* NAV */
        .nav-buttons { display:flex; justify-content:center; gap:12px; margin-bottom:28px; flex-wrap:wrap; }
        .nav-btn { padding:11px 20px; font-size:14px; font-weight:bold; border-radius:25px; text-decoration:none; color:white; box-shadow:0 4px 12px rgba(0,0,0,.2); transition:transform .2s,box-shadow .2s; }
        .nav-btn:hover { transform:translateY(-2px); box-shadow:0 6px 18px rgba(0,0,0,.3); }
        .nav-btn.home      { background:linear-gradient(45deg,var(--primary),var(--secondary)); }
        .nav-btn.y24       { background:linear-gradient(45deg,#ff6b6b,#ee5a52); }
        .nav-btn.y25       { background:linear-gradient(45deg,#4ecdc4,#44a08d); }
        .nav-btn.active    { background:linear-gradient(45deg,#333,#555); }

        /* SEARCH CARD */
        .search-card { background:white; border-radius:20px; padding:36px; box-shadow:0 8px 30px rgba(0,0,0,.1); margin-bottom:30px; text-align:center; }
        .search-card h2 { font-size:26px; font-weight:800; margin-bottom:8px; background:linear-gradient(135deg,var(--primary),var(--secondary)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
        .search-card .sub { color:#777; font-size:14px; margin-bottom:22px; }
        .search-form { display:flex; justify-content:center; align-items:center; gap:12px; flex-wrap:wrap; }
        .search-form input { font-size:19px; padding:13px 22px; width:300px; border:2px solid #ddd; border-radius:30px; outline:none; transition:all .3s; direction:ltr; }
        .search-form input:focus { border-color:var(--primary); box-shadow:0 0 12px rgba(102,126,234,.3); }
        .search-form button { font-size:17px; padding:13px 28px; border-radius:30px; border:none; cursor:pointer; background:linear-gradient(45deg,#f39c12,#8e44ad); color:white; font-weight:bold; box-shadow:0 4px 15px rgba(142,68,173,.4); transition:all .3s; }
        .search-form button:hover { transform:translateY(-2px); }

        /* STUDENT BANNER */
        .student-banner { background:linear-gradient(135deg,var(--primary),var(--secondary)); color:white; border-radius:16px; padding:22px 30px; margin-bottom:24px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; box-shadow:0 6px 20px rgba(102,126,234,.4); }
        .student-banner .s-name { font-size:22px; font-weight:900; }
        .student-banner .s-sub  { font-size:14px; opacity:.88; margin-top:3px; }
        .rank-badge { background:rgba(255,255,255,.22); border-radius:50%; width:82px; height:82px; display:flex; flex-direction:column; align-items:center; justify-content:center; font-weight:900; font-size:26px; border:3px solid rgba(255,255,255,.45); }
        .rank-badge small { font-size:10px; opacity:.8; }

        /* TABS */
        .tabs { display:flex; border-radius:14px; overflow:hidden; box-shadow:0 4px 15px rgba(0,0,0,.1); margin-bottom:24px; }
        .tab-btn { flex:1; padding:18px 10px; font-size:17px; font-weight:800; border:none; cursor:pointer; transition:all .25s; display:flex; align-items:center; justify-content:center; gap:8px; }
        .tab-btn.post   { background:#eafaf1; color:#1e8449; }
        .tab-btn.nopost { background:#fef9ef; color:#a04000; }
        .tab-btn.post.active   { background:linear-gradient(135deg,#27ae60,#2ecc71); color:white; box-shadow:inset 0 -4px 0 rgba(0,0,0,.15); }
        .tab-btn.nopost.active { background:linear-gradient(135deg,#e67e22,#f39c12); color:white; box-shadow:inset 0 -4px 0 rgba(0,0,0,.15); }
        .tab-btn .cnt { background:rgba(255,255,255,.3); border-radius:20px; padding:2px 10px; font-size:13px; }
        .tab-btn:not(.active) .cnt { background:rgba(0,0,0,.08); }

        /* STATS ROW */
        .stats-row { display:flex; gap:12px; justify-content:center; margin-bottom:18px; flex-wrap:wrap; }
        .stat-pill { padding:10px 20px; border-radius:50px; font-weight:bold; font-size:13px; display:flex; align-items:center; gap:7px; box-shadow:0 3px 10px rgba(0,0,0,.1); color:white; }
        .sp-total  { background:linear-gradient(45deg,var(--primary),var(--secondary)); }
        .sp-post   { background:linear-gradient(45deg,#27ae60,#2ecc71); }
        .sp-nopost { background:linear-gradient(45deg,#e67e22,#f39c12); }
        .sp-high   { background:linear-gradient(45deg,#2980b9,#3498db); }

        /* SEARCH + FILTER BAR */
        .filter-bar { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:16px; direction:ltr; }
        .filter-btn { padding:7px 16px; border-radius:18px; border:2px solid #ddd; background:white; cursor:pointer; font-size:13px; font-weight:bold; transition:all .2s; }
        .filter-btn.active, .filter-btn:hover { background:var(--primary); color:white; border-color:var(--primary); }
        .live-search { padding:7px 16px; border-radius:18px; border:2px solid #ddd; font-size:13px; outline:none; transition:all .2s; width:200px; }
        .live-search:focus { border-color:var(--primary); }

        /* TABLE */
        .table-wrap { overflow-x:auto; border-radius:14px; box-shadow:0 4px 20px rgba(0,0,0,.08); }
        table { width:100%; border-collapse:collapse; font-size:14px; background:white; }
        thead th { padding:14px 12px; font-size:15px; font-weight:700; text-align:center; position:sticky; top:0; z-index:5; color:white; }
        thead.post-head th   { background:linear-gradient(135deg,#27ae60,#2ecc71); }
        thead.nopost-head th { background:linear-gradient(135deg,#e67e22,#f39c12); }
        tbody td { padding:12px 12px; text-align:center; border-bottom:1px solid #f0f0f0; }
        tbody tr:hover { background:#fafafa; }
        tbody tr.rpost   { border-right:5px solid var(--green); }
        tbody tr.rnopost { border-right:5px solid var(--orange); }

        /* Probability bar */
        .prob-wrap { display:flex; align-items:center; gap:7px; justify-content:center; direction:ltr; }
        .bar-outer { flex:1; max-width:80px; height:8px; background:#e8e8e8; border-radius:4px; overflow:hidden; }
        .bar-inner { height:100%; border-radius:4px; }
        .phigh  .bar-inner { background:linear-gradient(90deg,#27ae60,#2ecc71); }
        .pmed   .bar-inner { background:linear-gradient(90deg,#f39c12,#f1c40f); }
        .plow   .bar-inner { background:linear-gradient(90deg,#e74c3c,#e67e22); }
        .prob-val { font-weight:800; font-size:14px; min-width:36px; }
        .phigh .prob-val { color:#27ae60; }
        .pmed  .prob-val { color:#e67e22; }
        .plow  .prob-val { color:#e74c3c; }

        /* Year pills */
        .ypill { display:inline-block; padding:2px 8px; border-radius:9px; font-size:11px; font-weight:bold; margin:1px; }
        .y2024 { background:#ffe0e0; color:#c0392b; }
        .y2025 { background:#d0f0ff; color:#1a6fa8; }

        .rrange { font-size:12px; color:#999; direction:ltr; display:inline-block; }
        .idx { font-weight:800; color:var(--primary); font-size:15px; }
        .spec-cell { text-align:right; font-weight:600; font-size:14px; direction:rtl; }
        .hosp-cell { font-size:12px; color:#666; direction:rtl; }

        /* Summary box */
        .summary { background:linear-gradient(135deg,#1a1a2e,#16213e); color:white; border-radius:14px; padding:24px 28px; margin-bottom:22px; border:1px solid rgba(255,255,255,.08); }
        .summary h3 { font-size:18px; margin-bottom:12px; display:flex; align-items:center; gap:7px; }
        .summary p  { font-size:14px; line-height:1.8; opacity:.9; }
        .chips { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }
        .chip { padding:5px 14px; border-radius:18px; font-size:12px; font-weight:bold; }
        .chip-g { background:rgba(39,174,96,.2); color:#2ecc71; border:1px solid rgba(46,204,113,.25); }
        .chip-o { background:rgba(230,126,34,.2); color:#f39c12; border:1px solid rgba(243,156,18,.25); }
        .chip-b { background:rgba(52,152,219,.2); color:#5dade2; border:1px solid rgba(93,173,226,.25); }

        /* Error */
        .error-box { background:#fde8e8; border:1px solid #f5c6c6; border-radius:12px; padding:22px; color:#c0392b; font-size:17px; font-weight:bold; margin:16px 0; text-align:center; }

        /* Palestine */
        .fp { margin-top:36px; padding:18px; border-radius:12px; background:linear-gradient(to right,black,white,green,red); color:white; font-size:22px; font-weight:bold; text-align:center; text-shadow:1px 1px 2px black; }

        /* Tab pane */
        .tab-pane { display:none; }
        .tab-pane.active { display:block; }

        @media(max-width:600px){
            .student-banner{flex-direction:column; text-align:center;}
            .search-form input{width:240px;}
        }
    </style>
</head>
<body>
<div class="container">

    <div class="header">
        <img src="https://i.postimg.cc/0rHzBdbx/8.jpg" alt="Logo">
        <div class="header-text">
            <h1><a href="/" style="text-decoration:none;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">AFM 26 Results &amp; Analysis</a></h1>
            <p><a href="https://t.me/Abdo_Hamdi6" target="_blank" style="text-decoration:none;background:linear-gradient(45deg,#ff6b6b,#4ecdc4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">By : Abdo Hamdy Aly</a></p>
        </div>
    </div>

    <div class="nav-buttons">
        <a href="/"                    class="nav-btn home">🏠 Home</a>
        <a href="/residency?year=2024" class="nav-btn y24">🏥 2024</a>
        <a href="/residency?year=2025" class="nav-btn y25">🏥 2025</a>
        <a href="/residency/predict"   class="nav-btn active">🤖 AI Prediction</a>
    </div>

    <!-- SEARCH -->
    <div class="search-card">
        <h2>🤖 AI Residency Prediction</h2>
        <p class="sub">أدخل رقم قيدك — هنحلل بيانات 2024 و 2025 ونحسب نسبة حصولك على كل تخصص (بوست ومن غير بوست بشكل منفصل)</p>
        <form class="search-form" method="POST" action="/residency/predict">
            <input type="text" name="student_id" placeholder="رقم القيد" value="{{ student_id or '' }}" required autocomplete="off">
            <button type="submit">🔍 ابحث</button>
        </form>
    </div>

    {% if error %}
        <div class="error-box">❌ {{ error }}</div>
    {% endif %}

    {% if post_preds is not none %}

    <!-- STUDENT BANNER -->
    <div class="student-banner">
        <div>
            <div class="s-name">👨‍⚕️ {{ student_name }}</div>
            <div class="s-sub">ID: {{ student_id }} &nbsp;|&nbsp; تحليل بيانات 2024 و 2025</div>
        </div>
        <div class="rank-badge"><small>RANK</small>#{{ student_rank }}</div>
    </div>

    <!-- SUMMARY -->
    <div class="summary">
        <h3>🧠 ملخص AI</h3>
        <p>
            بناءً على ترتيبك <strong>#{{ student_rank }}</strong> ، تم تحليل
            <strong>{{ post_preds|length }}</strong> تخصص بوست و
            <strong>{{ nopost_preds|length }}</strong> تخصص بدون بوست من بيانات 2024 &amp; 2025.
            {% set top3p = post_preds[:3] %}
            {% if top3p %}
                أفضل 3 تخصصات بوست ليك:
                <strong>{% for p in top3p %}{{ p.specialty }}{% if not loop.last %}, {% endif %}{% endfor %}</strong>
                بنسبة تصل لـ {{ top3p[0].probability }}%.
            {% endif %}
        </p>
        <div class="chips">
            <span class="chip chip-g">✅ {{ post_preds|length }} تخصص بوست</span>
            <span class="chip chip-o">📄 {{ nopost_preds|length }} تخصص بدون بوست</span>
            <span class="chip chip-b">📊 2024 &amp; 2025</span>
        </div>
    </div>

    <!-- STATS -->
    {% set post_high   = post_preds   | selectattr('probability','ge',60) | list | length %}
    {% set nopost_high = nopost_preds | selectattr('probability','ge',60) | list | length %}
    <div class="stats-row">
        <div class="stat-pill sp-post">✅ {{ post_preds|length }} بوست</div>
        <div class="stat-pill sp-nopost">📄 {{ nopost_preds|length }} بدون بوست</div>
        <div class="stat-pill sp-high">🔥 {{ post_high + nopost_high }} فرصة عالية (≥60%)</div>
    </div>

    <!-- TABS -->
    <div class="tabs">
        <button class="tab-btn post active" onclick="switchTab('post',this)">
            ✅ تخصصات بوست
            <span class="cnt">{{ post_preds|length }}</span>
        </button>
        <button class="tab-btn nopost" onclick="switchTab('nopost',this)">
            📄 بدون بوست
            <span class="cnt">{{ nopost_preds|length }}</span>
        </button>
    </div>

    <!-- ══ TAB: POST ══ -->
    <div id="pane-post" class="tab-pane active">
        <div class="filter-bar">
            <button class="filter-btn active" onclick="filt('post','all',this)">الكل</button>
            <button class="filter-btn"        onclick="filt('post','high',this)">🔥 أكتر من 60%</button>
            <button class="filter-btn"        onclick="filt('post','y25',this)">📅 ظهر في 2025</button>
            <input  class="live-search" id="post-search" oninput="lsearch('post')" placeholder="🔍 ابحث في التخصص...">
        </div>
        <div class="table-wrap">
            <table id="tbl-post">
                <thead class="post-head">
                    <tr>
                        <th>#</th>
                        <th>التخصص</th>
                        <th>المستشفى</th>
                        <th>% الحصول عليه</th>
                        <th>نطاق الـ Rank التاريخي</th>
                        <th>السنوات</th>
                    </tr>
                </thead>
                <tbody>
                {% for p in post_preds %}
                {% if p.probability >= 60 %}{% set pc='phigh' %}
                {% elif p.probability >= 30 %}{% set pc='pmed' %}
                {% else %}{% set pc='plow' %}{% endif %}
                <tr class="rpost"
                    data-prob="{{ p.probability }}"
                    data-spec="{{ p.specialty }}"
                    data-yrs="{{ p.years|join(',') }}">
                    <td class="idx">{{ loop.index }}</td>
                    <td class="spec-cell">{{ p.specialty }}</td>
                    <td class="hosp-cell">{{ p.hospital }}</td>
                    <td>
                        <div class="prob-wrap {{ pc }}">
                            <div class="bar-outer"><div class="bar-inner" style="width:{{ p.probability }}%"></div></div>
                            <span class="prob-val">{{ p.probability }}%</span>
                        </div>
                    </td>
                    <td><span class="rrange">{{ p.min_rank }} – {{ p.max_rank }}</span></td>
                    <td>{% for y in p.years %}<span class="ypill {{ 'y2024' if y=='2024' else 'y2025' }}">{{ y }}</span>{% endfor %}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- ══ TAB: NO POST ══ -->
    <div id="pane-nopost" class="tab-pane">
        <div class="filter-bar">
            <button class="filter-btn active" onclick="filt('nopost','all',this)">الكل</button>
            <button class="filter-btn"        onclick="filt('nopost','high',this)">🔥 أكتر من 60%</button>
            <button class="filter-btn"        onclick="filt('nopost','y25',this)">📅 ظهر في 2025</button>
            <input  class="live-search" id="nopost-search" oninput="lsearch('nopost')" placeholder="🔍 ابحث في التخصص...">
        </div>
        <div class="table-wrap">
            <table id="tbl-nopost">
                <thead class="nopost-head">
                    <tr>
                        <th>#</th>
                        <th>التخصص</th>
                        <th>المستشفى</th>
                        <th>% الحصول عليه</th>
                        <th>نطاق الـ Rank التاريخي</th>
                        <th>السنوات</th>
                    </tr>
                </thead>
                <tbody>
                {% for p in nopost_preds %}
                {% if p.probability >= 60 %}{% set pc='phigh' %}
                {% elif p.probability >= 30 %}{% set pc='pmed' %}
                {% else %}{% set pc='plow' %}{% endif %}
                <tr class="rnopost"
                    data-prob="{{ p.probability }}"
                    data-spec="{{ p.specialty }}"
                    data-yrs="{{ p.years|join(',') }}">
                    <td class="idx">{{ loop.index }}</td>
                    <td class="spec-cell">{{ p.specialty }}</td>
                    <td class="hosp-cell">{{ p.hospital }}</td>
                    <td>
                        <div class="prob-wrap {{ pc }}">
                            <div class="bar-outer"><div class="bar-inner" style="width:{{ p.probability }}%"></div></div>
                            <span class="prob-val">{{ p.probability }}%</span>
                        </div>
                    </td>
                    <td><span class="rrange">{{ p.min_rank }} – {{ p.max_rank }}</span></td>
                    <td>{% for y in p.years %}<span class="ypill {{ 'y2024' if y=='2024' else 'y2025' }}">{{ y }}</span>{% endfor %}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    {% endif %}

    <div class="fp">🇵🇸 FREE PALESTINE 🇵🇸</div>
</div>

<script>
// ── Tab switching ──
function switchTab(tab, btn) {
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('pane-' + tab).classList.add('active');
    btn.classList.add('active');
}

// ── Filter rows inside a tab ──
function filt(tab, type, btn) {
    // reset other buttons in same tab
    document.querySelectorAll('#pane-' + tab + ' .filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('#tbl-' + tab + ' tbody tr').forEach(r => {
        const prob = parseInt(r.dataset.prob);
        const yrs  = r.dataset.yrs || '';
        let show = true;
        if (type === 'high') show = prob >= 60;
        if (type === 'y25')  show = yrs.includes('2025');
        r.style.display = show ? '' : 'none';
    });
}

// ── Live search ──
function lsearch(tab) {
    const q = document.getElementById(tab + '-search').value.toLowerCase();
    document.querySelectorAll('#tbl-' + tab + ' tbody tr').forEach(r => {
        const spec = (r.dataset.spec || '').toLowerCase();
        r.style.display = spec.includes(q) ? '' : 'none';
    });
}
</script>
</body>
</html>
"""


# ──────────────────────────────────────────────────────────────────
#  ROUTES
# ──────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def main():
    mode = request.args.get('mode', 'search')
    result = None
    plot_url = None
    rank_progress_url = None
    percentile = None
    searched = False
    distance_result = None
    distance_searched = False
    need_result = None
    need_searched = False

    if request.method == 'POST':
        if mode == 'need':
            student_id = request.form.get('student_id')
            target_percentage = request.form.get('target_percentage')
            need_searched = True
            try:
                target_percentage = float(target_percentage)
                student_match = sheet1_df[sheet1_df['ID'].astype(str) == student_id]
                if not student_match.empty:
                    student_data = student_match.iloc[0]
                    student_name = student_data.get('NAME')
                    current_total_score = student_data.get('TOTAL', 0)
                    current_percentage = (current_total_score / 3630) * 100
                    required_total_score = (target_percentage / 100) * 4875
                    required_5th_year_score = required_total_score - current_total_score
                    required_5th_year_percentage = (required_5th_year_score / 1245) * 100
                    need_result = {
                        'student_name': student_name,
                        'current_percentage': round(current_percentage, 2) if pd.notna(current_percentage) else 0,
                        'target_percentage': target_percentage,
                        'required_5th_year_score': round(required_5th_year_score, 2) if pd.notna(required_5th_year_score) else 0,
                        'required_5th_year_percentage': round(required_5th_year_percentage, 2) if pd.notna(required_5th_year_percentage) else 0,
                    }
            except (ValueError, TypeError):
                need_result = None

        elif mode == 'distance':
            student_id = request.form.get('student_id')
            target_rank = request.form.get('target_rank')
            distance_searched = True
            try:
                target_rank = int(target_rank)
                student_match = sheet1_df[sheet1_df['ID'].astype(str) == student_id]
                if not student_match.empty:
                    student_data = student_match.iloc[0]
                    current_score = student_data.get('TOTAL')
                    student_name = student_data.get('NAME')
                    current_rank = (sheet1_df['TOTAL'] > current_score).sum() + 1
                    sorted_scores = sheet1_df.sort_values('TOTAL', ascending=False)
                    if target_rank <= len(sorted_scores):
                        target_score = sorted_scores.iloc[target_rank - 1]['TOTAL']
                        points_needed = target_score - current_score
                        distance_result = {
                            'student_name': student_name,
                            'current_rank': current_rank,
                            'target_rank': target_rank,
                            'points_needed': round(points_needed, 2) if pd.notna(points_needed) else 0,
                        }
            except (ValueError, IndexError):
                distance_result = None

        else:
            student_id = request.form['student_id']
            searched = True
            match = sheet1_df[sheet1_df['ID'].astype(str) == student_id]
            if not match.empty:
                raw_result = match.iloc[0].to_dict()
                formatted_result = {}
                for key, val in raw_result.items():
                    if isinstance(val, float):
                        if '%' in key.upper() or key.strip().upper() in ['%', 'PERCENTAGE']:
                            formatted_result[key] = f"{round(val * 100, 2)}%" if val <= 1 else f"{round(val, 2)}%"
                        elif val.is_integer():
                            formatted_result[key] = int(val)
                        else:
                            formatted_result[key] = round(val, 2)
                    else:
                        formatted_result[key] = val
                result = formatted_result

                total_scores = sheet1_df['TOTAL'].dropna()
                student_score = raw_result.get('TOTAL')

                if pd.notna(student_score):
                    percentile = round((total_scores < student_score).mean() * 100)
                    avg_score = total_scores.mean()
                    avg_percentage = (avg_score / 3630) * 100

                    plt.figure(figsize=(8, 5))
                    plt.hist(total_scores, bins=20, color='#66b3ff', edgecolor='black')
                    plt.axvline(student_score, color='orange', linestyle='solid', linewidth=2, label=f'Student Score: {student_score}')
                    plt.axvline(avg_score, color='black', linestyle='dashed', linewidth=2, label=f'Class Average ({round(avg_percentage, 2)}%)')
                    ymax = plt.gca().get_ylim()[1]
                    y_line = ymax * 0.7
                    plt.hlines(y_line, min(avg_score, student_score), max(avg_score, student_score), colors='red', linestyles='dashed', linewidth=2)
                    diff_percent = round(abs(student_score - avg_score) / 3630 * 100, 1)
                    mid_x = (student_score + avg_score) / 2
                    plt.text(mid_x, y_line + ymax * 0.03, f'{diff_percent}%', fontsize=10, fontweight='bold', ha='center', color='red')
                    plt.plot([], [], 'r--', label='% above/below average')
                    plt.xlabel('Scores'); plt.ylabel('Number of Students')
                    plt.title('Score Distribution with Student Highlighted')
                    plt.legend()
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png'); buf.seek(0)
                    plot_url = base64.b64encode(buf.getvalue()).decode('utf8')
                    buf.close(); plt.close()

                rank_match = sheet2_df[sheet2_df['ID'].astype(str) == student_id]
                rank_data = rank_match.iloc[0].to_dict() if not rank_match.empty else {}

                rank_columns = {
                    "FIRST YEAR RANK":    ("FIRST YEAR",  "#e0f7fa"),
                    "SECOND YEAR RANK C": ("SECOND YEAR", "#fff3e0"),
                    "THIRD YEAR RANK C":  ("THIRD YEAR",  "#ede7f6"),
                    "FOURTH YEAR RANK C": ("FOURTH YEAR", "#d0e0ff"),
                }
                progress_labels = []; rank_values = []; colors = []
                for col, (label, color) in rank_columns.items():
                    rank = rank_data.get(col)
                    if pd.notna(rank):
                        progress_labels.append(label); rank_values.append(rank); colors.append(color)

                if progress_labels and rank_values:
                    plt.figure(figsize=(8, 5))
                    plt.plot(progress_labels, rank_values, marker='o', linestyle='-', color='black', linewidth=2)
                    for i in range(len(progress_labels)):
                        plt.plot(progress_labels[i], rank_values[i], '3', markersize=10, color=colors[i])
                        plt.text(progress_labels[i], rank_values[i] + 0.5, f'{int(rank_values[i])}',
                                 ha='center', va='top', fontsize=14, fontweight='bold', color='black',
                                 bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='black'))
                        if i > 0:
                            change = rank_values[i - 1] - rank_values[i]
                            color = 'green' if change > 0 else 'red'
                            sign  = '+' if change > 0 else ''
                            arrow = '⬆' if change > 0 else '⬇'
                            mid_x = i - 0.5
                            mid_y = (rank_values[i - 1] + rank_values[i]) / 2
                            plt.text(mid_x, mid_y + 2.5, f'{arrow} {sign}{abs(int(change))}',
                                     fontsize=11, fontweight='bold', color=color, ha='center', va='top',
                                     bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor=color))
                    plt.ylabel('Cumulative Rank'); plt.title('Cumulative Progress Based on Class Rank')
                    plt.gca().invert_yaxis(); plt.grid(True)
                    buf = io.BytesIO()
                    plt.savefig(buf, format='png'); buf.seek(0)
                    rank_progress_url = base64.b64encode(buf.getvalue()).decode('utf8')
                    buf.close(); plt.close()

    return render_template_string(html_template,
                                  mode=mode, result=result, plot_url=plot_url,
                                  rank_progress_url=rank_progress_url, percentile=percentile,
                                  searched=searched, distance_result=distance_result,
                                  distance_searched=distance_searched, need_result=need_result,
                                  need_searched=need_searched)


@app.route('/residency', methods=['GET'])
def residency_matching():
    year = request.args.get('year', '2024')
    df = residency_25_df if year == '2025' else residency_24_df
    results = []; boast_count = 0; no_boast_count = 0
    if not df.empty:
        results = df.to_dict('records')
        for row in results:
            status = str(row.get('STATUS', ''))
            if status.strip() == 'بوست':
                boast_count += 1
            elif status.strip() == 'بدون بوست':
                no_boast_count += 1
    return render_template_string(residency_template,
                                  year=year, results=results, df_empty=df.empty,
                                  boast_count=boast_count, no_boast_count=no_boast_count)


@app.route('/residency/predict', methods=['GET', 'POST'])
def residency_predict():
    post_preds   = None
    nopost_preds = None
    student_name = None
    student_rank = None
    student_id   = None
    error        = None

    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        if not student_id:
            error = 'يرجى إدخال رقم القيد.'
        else:
            match = sheet1_df[sheet1_df['ID'].astype(str) == student_id]
            if match.empty:
                error = f'رقم القيد "{student_id}" غير موجود. تحقق من الرقم وحاول مرة أخرى.'
            else:
                student_data = match.iloc[0]
                student_name = student_data.get('NAME', 'Unknown')
                total = student_data.get('TOTAL')
                if pd.isna(total):
                    error = 'لا يمكن تحديد الترتيب — درجة TOTAL مفقودة.'
                else:
                    total_scores = sheet1_df['TOTAL'].dropna()
                    student_rank = int((total_scores > total).sum()) + 1
                    post_preds, nopost_preds = get_residency_predictions(
                        student_rank, residency_24_df, residency_25_df
                    )

    return render_template_string(ai_predict_template,
                                  post_preds=post_preds,
                                  nopost_preds=nopost_preds,
                                  student_name=student_name,
                                  student_rank=student_rank,
                                  student_id=student_id,
                                  error=error)


if __name__ == '__main__':
    app.run(debug=True)
