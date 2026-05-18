from flask import Flask, render_template_string, request
import os, json, requests
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


def get_summary_top3(post_preds):
    """
    Pick the best 3 specialties for the summary banner.
    Uses geometric mean of probability × prestige so BOTH must be good.
    - Low probability kills the score even if prestige is high.
    - Low prestige (high min_rank) is penalized even if probability is high.
    Prestige has a floor of 0.15 so it never zeroes out completely.
    """
    if not post_preds:
        return []
    max_min_rank = max(p['min_rank'] for p in post_preds) or 1
    scored = []
    for p in post_preds:
        prob_norm = p['probability'] / 100
        # prestige: 1.0 for min_rank=1, floors at 0.15 for highest min_rank
        prestige  = 0.15 + 0.85 * (1 - p['min_rank'] / max_min_rank)
        # geometric mean — both factors must be strong
        score     = prob_norm * prestige
        scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:3]]


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
            <a href="/residency/specialty" class="nav-btn" style="background:linear-gradient(45deg,#1a1a2e,#16213e);">🧭 What Is My Specialty?</a>
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
            <a href="/residency/predict"   class="nav-btn ai-predict">🏥 Prediction</a>
            <a href="/residency/specialty" class="nav-btn" style="background:linear-gradient(45deg,#1a1a2e,#16213e);">🧭 What Is My Specialty?</a>
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
    <title>Residency Prediction</title>
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
        .nav-btn { padding:12px 22px; font-size:15px; font-weight:bold; border-radius:25px; text-decoration:none; color:white; box-shadow:0 4px 12px rgba(0,0,0,.2); transition:transform .2s,box-shadow .2s; white-space:nowrap; }
        .nav-btn:hover { transform:translateY(-2px); box-shadow:0 6px 18px rgba(0,0,0,.3); }
        .nav-btn.home      { background:linear-gradient(45deg,var(--primary),var(--secondary)); }
        .nav-btn.y24       { background:linear-gradient(45deg,#ff6b6b,#ee5a52); }
        .nav-btn.y25       { background:linear-gradient(45deg,#4ecdc4,#44a08d); }
        .nav-btn.active    { background:linear-gradient(45deg,#333,#555); }

        /* SEARCH CARD */
        .search-card { background:white; border-radius:20px; padding:32px 36px 28px; box-shadow:0 8px 30px rgba(0,0,0,.1); margin-bottom:30px; text-align:center; }
        .search-card h2 { font-size:26px; font-weight:800; margin-bottom:20px; background:linear-gradient(135deg,var(--primary),var(--secondary)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
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
        <a href="/"                    class="nav-btn home">🏠 الرئيسية</a>
        <a href="/residency?year=2025" class="nav-btn y25">🏥 2025</a>
        <a href="/residency?year=2024" class="nav-btn y24">🏥 2024</a>
        <a href="/residency/predict"   class="nav-btn active">🏥 Prediction</a>
        <a href="/residency/specialty" class="nav-btn" style="background:linear-gradient(45deg,#1a1a2e,#16213e);">🧭 What Is My Specialty?</a>
    </div>

    <!-- SEARCH -->
    <div class="search-card">
        <h2>🏥 Residency Prediction</h2>
        <form class="search-form" method="POST" action="/residency/predict">
            <input type="text" name="student_id" placeholder="رقم الجلوس" value="{{ student_id or '' }}" required autocomplete="off">
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
        <h3>📊 ملخص</h3>
        <p>
            بناءً على ترتيبك <strong>#{{ student_rank }}</strong> ، تم تحليل
            <strong>{{ post_preds|length }}</strong> تخصص بوست و
            <strong>{{ nopost_preds|length }}</strong> تخصص بدون بوست من بيانات 2024 &amp; 2025.
            {% if summary_top3 %}
                أفضل تخصصات بوست ليك جمعاً بين النسبة والتنافسية:
                <strong>{% for p in summary_top3 %}{{ p.specialty }}{% if not loop.last %}, {% endif %}{% endfor %}</strong>.
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

    summary_top3 = get_summary_top3(post_preds) if post_preds else []

    return render_template_string(ai_predict_template,
                                  post_preds=post_preds,
                                  nopost_preds=nopost_preds,
                                  summary_top3=summary_top3,
                                  student_name=student_name,
                                  student_rank=student_rank,
                                  student_id=student_id,
                                  error=error)



# ─────────────────────────────────────────────────────────────────
#  SPECIALTY QUIZ — What Is My Specialty?
# ─────────────────────────────────────────────────────────────────

GROQ_API_KEY  = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL    = "openai/gpt-oss-120b"
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

SPECIALTY_META = {
    'cardiology':    ('قلب وأوعية دموية',         '❤️',  'Cardiology'),
    'cardiac_surg':  ('جراحة قلب وصدر',           '🫀',  'Cardiac Surgery'),
    'ophth':         ('طب وجراحة العيون',           '👁️',  'Ophthalmology'),
    'derm':          ('جلدية',                     '✨',  'Dermatology'),
    'plastic':       ('جراحة تجميل',               '💎',  'Plastic Surgery'),
    'obgyn':         ('نسا وتوليد',               '🌸',  'OB/GYN'),
    'peds':          ('أطفال',                    '🧒',  'Pediatrics'),
    'radiology':     ('أشعة تشخيصية',             '🔬',  'Radiology'),
    'internal':      ('باطنة',                    '🏥',  'Internal Medicine'),
    'surgery':       ('جراحة',                    '⚕️',  'General Surgery'),
    'ortho':         ('جراحة عظام',               '🦴',  'Orthopedics'),
    'anesth':        ('تخدير',                    '💉',  'Anesthesia'),
    'neurosurg':     ('جراحة مخ وأعصاب',          '🧠',  'Neurosurgery'),
    'neurology':     ('نفسية وعصبية',             '🧬',  'Neurology/Psych'),
    'ent':           ('أنف وأذن وحنجرة',          '👂',  'ENT'),
    'pulm':          ('صدرية',                    '🫁',  'Pulmonology'),
    'oncology':      ('علاج الأورام والطب النووي', '🎗️',  'Oncology'),
    'pathology':     ('باثولوجي',                 '🔭',  'Pathology'),
    'clinical_path': ('كلينيكال باثولوجي',         '🧪',  'Clinical Pathology'),
    'emergency':     ('طوارئ',                    '🚨',  'Emergency Medicine'),
    'urology':       ('جراحة مسالك',              '🫘',  'Urology'),
    'rheum':         ('طب طبيعي',                 '💊',  'Rheumatology/PT'),
}

SPECIALTY_TO_ARABIC_ALIASES = {
    'cardiology':    ['قلب وأوعية دموية','القلب والأوعية الدموية','أمراض القلب'],
    'cardiac_surg':  ['جراحة قلب وصدر','جراحة القلب والصدر'],
    'ophth':         ['طب وجراحة العيون'],
    'derm':          ['جلدية','الأمراض الجلدية والتناسلية وأمراض الذكورة'],
    'plastic':       ['جراحة تجميل','جراحة التجميل'],
    'obgyn':         ['نسا وتوليد','أمراض النساء والتوليد'],
    'peds':          ['أطفال','طب الأطفال'],
    'radiology':     ['أشعة تشخيصية','الأشعة التشخيصية','أشعة'],
    'internal':      ['باطنة','الباطنة العامة','باطنة روماتيزم','باطنة كلى',
                      'باطنة غدد','باطنة دم','باطنة جهاز هضمي','باطنة كبد'],
    'surgery':       ['جراحة','الجراحة العامة','جراحة عامة'],
    'ortho':         ['جراحة عظام','جراحة العظام والإصابات'],
    'anesth':        ['تخدير','تخدير وعناية','التخدير وعلاج الألم'],
    'neurosurg':     ['جراحة مخ وأعصاب','جراحة المخ والاعصاب'],
    'neurology':     ['نفسية وعصبية','أمراض المخ والأعصاب والطب النفسي'],
    'ent':           ['أنف وأذن وحنجرة','الأنف والأذن والحنجرة'],
    'pulm':          ['صدرية','الأمراض الصدرية'],
    'oncology':      ['علاج الأورام والطب النووي','علاج ابحاث الأورام'],
    'pathology':     ['باثولوجي','الباثولوجيا'],
    'clinical_path': ['كلينيكال باثولوجي','الباثولوجيا الإكلينيكية'],
    'emergency':     ['طوارئ','طب الطوارئ'],
    'urology':       ['جراحة مسالك','جراحة المسالك البولية'],
    'rheum':         ['طب طبيعي','الروماتيزم والتأهيل والطب الطبيعي'],
}

QUIZ_QUESTIONS = [
    # Section 1
    {"id":"q1","section":"Work Style","section_num":1,
     "text":"Which best describes your ideal workday?",
     "options":[
       {"id":"a","text":"🔪 Performing complex procedures or surgeries in an operating room"},
       {"id":"b","text":"🩺 Seeing patients in clinic and building long-term relationships"},
       {"id":"c","text":"🔬 Analyzing data, images, or lab results — less direct patient contact"},
       {"id":"d","text":"🚨 Responding to emergencies and rapidly changing, high-pressure situations"},
     ]},
    {"id":"q2","section":"Work Style","section_num":1,
     "text":"How do you feel about manual dexterity and intricate technical procedures?",
     "options":[
       {"id":"a","text":"🤌 I love working with my hands — the more detailed and technical, the better"},
       {"id":"b","text":"⚖️ I enjoy a healthy mix of hands-on work and cognitive thinking"},
       {"id":"c","text":"🧠 I'd rather focus on intellectual reasoning than on manual procedures"},
     ]},
    {"id":"q3","section":"Work Style","section_num":1,
     "text":"What kind of patient interaction suits you best?",
     "options":[
       {"id":"a","text":"⚡ Brief, focused encounters — patients come in, I solve the problem, they leave"},
       {"id":"b","text":"💛 Long-term relationships — watching patients improve over months or years"},
       {"id":"c","text":"🔭 Minimal direct patient contact — I prefer lab, imaging, or analytical work"},
       {"id":"d","text":"🔄 A mix — variety is key, I enjoy both acute and chronic"},
     ]},
    {"id":"q4","section":"Work Style","section_num":1,
     "text":"How important is a predictable schedule and work-life balance to you?",
     "options":[
       {"id":"a","text":"🏠 Very important — I need time for family, hobbies, and a personal life"},
       {"id":"b","text":"🤷 Somewhat — I can handle demanding hours if the work is truly meaningful"},
       {"id":"c","text":"🔥 Not a priority — I'm willing to sacrifice personal time to master my specialty"},
     ]},
    {"id":"q5","section":"Work Style","section_num":1,
     "text":"How do you feel about frequent night shifts, weekends on-call, and interrupted sleep?",
     "options":[
       {"id":"a","text":"⚡ I thrive in overnight emergency work — the adrenaline sharpens my focus"},
       {"id":"b","text":"😴 I can handle it occasionally, but strongly prefer mainly daytime work"},
       {"id":"c","text":"🌞 I strongly prefer a predictable, scheduled daytime-only work pattern"},
     ]},
    # Section 2
    {"id":"q6","section":"Clinical Interests","section_num":2,
     "text":"Which organ system or clinical area excites you the most?",
     "options":[
       {"id":"a","text":"❤️ Heart & blood vessels — cardiology or cardiac surgery"},
       {"id":"b","text":"🧠 Brain, nerves & the mind — neurology, neurosurgery, or psychiatry"},
       {"id":"c","text":"🦴 Bones, joints & movement — orthopedics or rheumatology"},
       {"id":"d","text":"👁️ Sensory organs — eyes (ophthalmology) or ears/nose/throat (ENT)"},
       {"id":"e","text":"🌿 Internal systems — skin, lungs, kidneys, GI, hormones, or urinary"},
       {"id":"f","text":"🌸 Female reproductive health — obstetrics, gynecology & pregnancy"},
       {"id":"g","text":"🧒 Children's health — pediatrics or pediatric surgery"},
       {"id":"h","text":"🔬 Cells, tissues & disease under the microscope — pathology or lab medicine"},
     ]},
    {"id":"q7","section":"Clinical Interests","section_num":2,
     "text":"Medical or surgical management — which do you naturally lean toward?",
     "options":[
       {"id":"a","text":"💊 Medical — medications, clinical reasoning, and non-invasive management"},
       {"id":"b","text":"🔪 Surgical — fixing problems with my hands; I love the idea of an operation"},
       {"id":"c","text":"🔄 Both — I enjoy specialties that blend medical and surgical approaches"},
     ]},
    {"id":"q8","section":"Clinical Interests","section_num":2,
     "text":"Do you prefer acute, rapidly changing conditions or chronic long-term care?",
     "options":[
       {"id":"a","text":"⚡ Acute — rapid decisions, immediate outcomes, fast-paced environment"},
       {"id":"b","text":"📈 Chronic — guiding patients over time, watching steady long-term progress"},
       {"id":"c","text":"🔀 Both — I value variety; mixing acute episodes with ongoing care"},
     ]},
    {"id":"q9","section":"Clinical Interests","section_num":2,
     "text":"Do you prefer working with adults, children, or does it not matter?",
     "options":[
       {"id":"a","text":"👨 Mostly adults — I connect better with adult patients"},
       {"id":"b","text":"🧒 Children and adolescents — I'm genuinely drawn to working with kids"},
       {"id":"c","text":"🔄 No strong preference — I can adapt to any age group"},
     ]},
    {"id":"q10","section":"Clinical Interests","section_num":2,
     "text":"How much do you enjoy interpreting images — X-rays, CT, MRI, or pathology slides?",
     "options":[
       {"id":"a","text":"🔍 I love it — visual pattern recognition genuinely excites me"},
       {"id":"b","text":"😊 I find it interesting but wouldn't want it as my primary daily task"},
       {"id":"c","text":"😐 Not really — I prefer direct patient contact and clinical work"},
     ]},
    # Section 3
    {"id":"q11","section":"Personality & Values","section_num":3,
     "text":"How comfortable are you with regularly delivering bad news or caring for dying patients?",
     "options":[
       {"id":"a","text":"💪 Very comfortable — I'm emotionally resilient; it's core to medicine"},
       {"id":"b","text":"😔 I can handle it occasionally, but prefer it to be less frequent"},
       {"id":"c","text":"🛡️ I'd prefer a field where I rarely face end-of-life or emotionally heavy cases"},
     ]},
    {"id":"q12","section":"Personality & Values","section_num":3,
     "text":"What motivates you most about practicing medicine?",
     "options":[
       {"id":"a","text":"✅ Visible, immediate results — the patient walks out healed or surgery succeeds"},
       {"id":"b","text":"🧩 Intellectual challenge — cracking complex diagnostic puzzles that stump others"},
       {"id":"c","text":"🔭 Research and discovery — contributing to science and new medical knowledge"},
       {"id":"d","text":"❤️ Caring for vulnerable people — making patients feel safe, heard, supported"},
     ]},
    {"id":"q13","section":"Personality & Values","section_num":3,
     "text":"How do you perform in high-stress, life-or-death situations?",
     "options":[
       {"id":"a","text":"🔥 I perform BEST under pressure — stress sharpens my focus"},
       {"id":"b","text":"🧘 I prefer calm, controlled, steady work environments without daily crises"},
       {"id":"c","text":"⚖️ I can handle high-stakes moments occasionally, but not daily"},
     ]},
    {"id":"q14","section":"Personality & Values","section_num":3,
     "text":"Where do you realistically see yourself professionally in 15 years?",
     "options":[
       {"id":"a","text":"🏆 A technically elite expert in a highly specialized, demanding field"},
       {"id":"b","text":"🏥 A trusted clinician with a large, loyal patient base"},
       {"id":"c","text":"📚 An academic — researcher, professor, or department head"},
       {"id":"d","text":"💼 Running my own successful private practice"},
     ]},
    {"id":"q15","section":"Personality & Values","section_num":3,
     "text":"What is your biggest professional fear as a future doctor?",
     "options":[
       {"id":"a","text":"🔪 Making a technical error during a complex procedure that harms a patient"},
       {"id":"b","text":"🔍 Missing a critical diagnosis and sending the wrong patient home"},
       {"id":"c","text":"💔 Being emotionally overwhelmed by constant patient suffering and death"},
       {"id":"d","text":"🕐 Having no life outside medicine — missing family milestones due to overwork"},
     ]},
    # Section 4
    {"id":"q16","section":"Scenarios & Goals","section_num":4,
     "text":"Which subject genuinely excited you most during medical school?",
     "options":[
       {"id":"a","text":"🔪 Surgery, operative anatomy, and surgical techniques"},
       {"id":"b","text":"🏥 Internal medicine, clinical reasoning, and pathophysiology"},
       {"id":"c","text":"🧒 Pediatrics and child health and development"},
       {"id":"d","text":"🌸 Obstetrics, gynecology, and reproductive medicine"},
       {"id":"e","text":"🧠 Psychiatry, neurology, and neurological disorders"},
       {"id":"f","text":"📡 Radiology, imaging interpretation, and diagnostic techniques"},
       {"id":"g","text":"🔬 Pathology, microbiology, biochemistry, or basic sciences"},
       {"id":"h","text":"💊 Pharmacology, oncology, immunology, or therapeutics"},
     ]},
    {"id":"q17","section":"Scenarios & Goals","section_num":4,
     "text":"In a ward round with a complex patient, what role do you naturally gravitate toward?",
     "options":[
       {"id":"a","text":"🖐️ I'm the one who jumps in to do procedures — lines, intubation, suturing"},
       {"id":"b","text":"🧠 I focus on building the differential diagnosis and clinical reasoning"},
       {"id":"c","text":"🤝 I prioritize talking to the patient and family first"},
       {"id":"d","text":"📊 I immediately check the labs, imaging, and monitoring data"},
     ]},
    {"id":"q18","section":"Scenarios & Goals","section_num":4,
     "text":"Which scenario sounds most personally rewarding to YOU?",
     "options":[
       {"id":"a","text":"⚔️ Executing a technically perfect, high-risk surgery that saves a life"},
       {"id":"b","text":"🔍 Cracking a mysterious diagnosis after weeks when all others failed"},
       {"id":"c","text":"👶 Safely delivering a healthy baby in a complicated, life-threatening pregnancy"},
       {"id":"d","text":"🎗️ Guiding a cancer patient through treatment until they're in remission"},
       {"id":"e","text":"👁️ Restoring someone's eyesight, hearing, or ability to walk"},
     ]},
    {"id":"q19","section":"Scenarios & Goals","section_num":4,
     "text":"Which personality type best describes you?",
     "options":[
       {"id":"a","text":"🦅 The Doer — action-oriented, decisive, thrives with concrete tasks"},
       {"id":"b","text":"🦉 The Thinker — analytical, methodical, loves solving complex challenges"},
       {"id":"c","text":"🦋 The Nurturer — empathetic, people-focused, driven by human connection"},
       {"id":"d","text":"🔭 The Observer — detail-oriented, systematic, prefers careful analysis"},
     ]},
    {"id":"q20","section":"Scenarios & Goals","section_num":4,
     "text":"If you could achieve ONE legacy in your medical career, it would be:",
     "options":[
       {"id":"a","text":"✂️ Performing cutting-edge surgeries that very few doctors in Egypt can do"},
       {"id":"b","text":"🔍 Being the doctor who solves medical cases that stump every other specialist"},
       {"id":"c","text":"💛 Being remembered as the doctor who truly cared and never gave up"},
       {"id":"d","text":"🔬 Publishing research that changes how doctors worldwide treat a disease"},
       {"id":"e","text":"🏠 Building a respected practice where patients come from far away just for you"},
     ]},
]

QUIZ_WEIGHTS = {
    'q1':{
        'a':{'surgery':10,'cardiac_surg':9,'ortho':9,'neurosurg':9,'plastic':9,'ophth':8,'urology':8,'ent':7,'anesth':6},
        'b':{'internal':10,'derm':9,'cardiology':8,'peds':9,'obgyn':7,'neurology':9,'rheum':8,'pulm':7},
        'c':{'radiology':12,'pathology':12,'clinical_path':11},
        'd':{'emergency':12,'anesth':8,'cardiology':6,'surgery':5},
    },
    'q2':{
        'a':{'surgery':10,'ophth':10,'ortho':10,'neurosurg':9,'cardiac_surg':9,'plastic':10,'urology':8,'ent':8},
        'b':{'cardiology':6,'obgyn':7,'anesth':7,'peds':5,'ent':6,'urology':6,'emergency':5},
        'c':{'internal':8,'neurology':8,'radiology':9,'pathology':9,'derm':7,'emergency':6},
    },
    'q3':{
        'a':{'anesth':9,'emergency':9,'surgery':8,'radiology':7},
        'b':{'internal':10,'derm':9,'cardiology':8,'neurology':9,'peds':9,'obgyn':8,'rheum':9,'pulm':8},
        'c':{'radiology':10,'pathology':11,'clinical_path':10},
        'd':{'ent':8,'ophth':8,'urology':7,'cardiology':5,'obgyn':5},
    },
    'q4':{
        'a':{'derm':9,'radiology':9,'pathology':9,'clinical_path':8,'rheum':7,'ent':6,'ophth':6},
        'b':{'internal':7,'cardiology':6,'peds':7,'ent':6,'urology':6,'pulm':6,'obgyn':5},
        'c':{'surgery':9,'neurosurg':9,'cardiac_surg':9,'plastic':8,'oncology':8,'cardiology':5},
    },
    'q5':{
        'a':{'emergency':11,'surgery':8,'cardiac_surg':8,'neurosurg':8,'anesth':9,'cardiology':6,'ortho':6},
        'b':{'internal':7,'peds':7,'obgyn':8,'ortho':6,'pulm':5,'urology':5},
        'c':{'derm':10,'radiology':9,'pathology':9,'rheum':8,'ophth':6,'clinical_path':8},
    },
    'q6':{
        'a':{'cardiology':12,'cardiac_surg':11},
        'b':{'neurology':12,'neurosurg':11},
        'c':{'ortho':12,'rheum':10},
        'd':{'ophth':11,'ent':11},
        'e':{'internal':7,'derm':8,'pulm':9,'urology':8,'surgery':6},
        'f':{'obgyn':14},
        'g':{'peds':14},
        'h':{'pathology':12,'clinical_path':11},
    },
    'q7':{
        'a':{'internal':9,'cardiology':8,'neurology':7,'derm':9,'rheum':9,'pulm':9,'oncology':8},
        'b':{'surgery':10,'ortho':10,'neurosurg':10,'cardiac_surg':10,'plastic':10,'obgyn':7,'urology':9,'ent':8,'ophth':9},
        'c':{'anesth':8,'emergency':7,'ent':7,'urology':7,'ophth':7,'obgyn':7,'cardiology':5},
    },
    'q8':{
        'a':{'emergency':11,'surgery':9,'anesth':9,'cardiac_surg':9,'neurosurg':8,'ortho':7,'cardiology':6},
        'b':{'internal':9,'cardiology':8,'neurology':8,'derm':9,'oncology':8,'rheum':8,'pulm':7},
        'c':{'peds':8,'obgyn':8,'ent':7,'pulm':7,'urology':7,'ophth':6},
    },
    'q9':{
        'a':{'internal':7,'surgery':7,'cardiology':7,'derm':7,'neurology':7,'urology':7,'ortho':7,'rheum':6,'oncology':6,'pulm':7},
        'b':{'peds':14},
        'c':{'obgyn':8,'emergency':7,'ent':6,'anesth':6,'radiology':5},
    },
    'q10':{
        'a':{'radiology':13,'pathology':12,'clinical_path':11},
        'b':{'cardiology':6,'neurology':6,'oncology':6,'ophth':5},
        'c':{'internal':6,'surgery':6,'peds':6,'obgyn':6,'derm':5,'emergency':5},
    },
    'q11':{
        'a':{'oncology':11,'emergency':9,'anesth':8,'internal':7,'surgery':7,'neurology':6},
        'b':{'peds':7,'obgyn':7,'cardiology':5,'pulm':5,'surgery':5},
        'c':{'derm':9,'radiology':9,'pathology':9,'ent':7,'ophth':7,'clinical_path':8},
    },
    'q12':{
        'a':{'surgery':9,'emergency':9,'anesth':8,'ortho':8,'plastic':9,'ophth':8,'cardiac_surg':8},
        'b':{'internal':10,'neurology':9,'radiology':9,'pathology':8,'cardiology':7},
        'c':{'pathology':9,'clinical_path':8,'oncology':8,'internal':5,'radiology':5},
        'd':{'peds':9,'obgyn':8,'oncology':7,'neurology':6},
    },
    'q13':{
        'a':{'emergency':11,'surgery':9,'cardiac_surg':9,'anesth':9,'ortho':7,'neurosurg':8},
        'b':{'radiology':9,'pathology':9,'derm':8,'rheum':7,'clinical_path':8},
        'c':{'internal':7,'cardiology':7,'peds':7,'pulm':6,'neurology':6},
    },
    'q14':{
        'a':{'surgery':8,'neurosurg':8,'cardiac_surg':8,'plastic':7,'ophth':7,'ortho':7},
        'b':{'internal':8,'cardiology':8,'peds':8,'derm':8,'obgyn':7,'pulm':7},
        'c':{'pathology':9,'clinical_path':8,'radiology':7,'oncology':6},
        'd':{'derm':8,'ent':6,'ophth':7,'emergency':5,'urology':5},
    },
    'q15':{
        'a':{'surgery':8,'neurosurg':8,'cardiac_surg':8,'plastic':7},
        'b':{'internal':8,'neurology':7,'radiology':6,'cardiology':6},
        'c':{'derm':8,'radiology':8,'pathology':8,'ent':6,'ophth':6},
        'd':{'derm':8,'radiology':7,'pathology':7,'clinical_path':7,'emergency':5},
    },
    'q16':{
        'a':{'surgery':11,'ortho':10,'neurosurg':9,'plastic':9,'cardiac_surg':8},
        'b':{'internal':11,'cardiology':9,'neurology':8,'pulm':8,'rheum':7},
        'c':{'peds':13},
        'd':{'obgyn':13},
        'e':{'neurology':12},
        'f':{'radiology':13},
        'g':{'pathology':12,'clinical_path':11},
        'h':{'oncology':10,'rheum':7,'internal':5},
    },
    'q17':{
        'a':{'surgery':9,'emergency':9,'anesth':8,'ortho':8,'neurosurg':7},
        'b':{'internal':10,'neurology':9,'cardiology':8,'pulm':7,'radiology':5},
        'c':{'obgyn':9,'peds':9,'oncology':8,'neurology':7},
        'd':{'radiology':10,'clinical_path':9,'pathology':9,'cardiology':5},
    },
    'q18':{
        'a':{'surgery':10,'neurosurg':10,'cardiac_surg':10,'plastic':9,'ophth':9},
        'b':{'internal':10,'neurology':9,'radiology':8,'cardiology':7},
        'c':{'obgyn':13},
        'd':{'oncology':12,'peds':8},
        'e':{'ophth':11,'ent':10,'ortho':9,'neurosurg':7},
    },
    'q19':{
        'a':{'surgery':9,'emergency':9,'ortho':8,'cardiac_surg':7,'anesth':8,'neurosurg':7},
        'b':{'internal':10,'neurology':9,'cardiology':7,'radiology':6,'pathology':6},
        'c':{'peds':10,'oncology':9,'obgyn':8,'neurology':7},
        'd':{'radiology':11,'clinical_path':9,'pathology':10,'derm':6},
    },
    'q20':{
        'a':{'surgery':10,'neurosurg':10,'cardiac_surg':10,'plastic':9,'ophth':9},
        'b':{'internal':10,'neurology':9,'radiology':8,'pathology':7},
        'c':{'peds':9,'oncology':9,'obgyn':7,'neurology':7},
        'd':{'pathology':9,'oncology':8,'clinical_path':8,'internal':5},
        'e':{'derm':9,'ent':8,'ophth':8,'internal':6,'cardiology':5},
    },
}

def compute_specialty_scores(answers):
    scores = {k: 0 for k in SPECIALTY_META}
    for qid, opt in answers.items():
        if qid in QUIZ_WEIGHTS and opt in QUIZ_WEIGHTS[qid]:
            for spec, pts in QUIZ_WEIGHTS[qid][opt].items():
                if spec in scores:
                    scores[spec] += pts
    mx = max(scores.values()) if any(scores.values()) else 1
    return {k: round(v / mx * 100) for k, v in scores.items()}

def get_availability_for_spec(post_preds, nopost_preds, spec_key):
    aliases = SPECIALTY_TO_ARABIC_ALIASES.get(spec_key, [])
    best = 0
    for pred_list in [post_preds or [], nopost_preds or []]:
        for pred in pred_list:
            spec_ar = str(pred.get('specialty', ''))
            prob    = pred.get('probability', 0)
            for alias in aliases:
                if alias in spec_ar or spec_ar in alias:
                    if prob > best:
                        best = prob
                    break
    return round(best)

def build_groq_prompt(student_name, student_rank, total_students, answers, top_specs):
    q_map = {q['id']: q for q in QUIZ_QUESTIONS}
    lines = []
    for i in range(1, 21):
        qid = f'q{i}'
        opt = answers.get(qid)
        if not opt or qid not in q_map:
            continue
        q = q_map[qid]
        opt_map = {o['id']: o['text'] for o in q['options']}
        lines.append(f"Q{i} [{q['section']}]: {q['text']}\n   -> {opt_map.get(opt, opt)}")

    top_text = '\n'.join(
        f"  {i+1}. {SPECIALTY_META[sk][2]} ({SPECIALTY_META[sk][0]}) "
        f"— Interest {sc['interest']}%, Availability {sc['availability']}%, Combined {sc['combined']}%"
        for i, (sk, sc) in enumerate(top_specs)
    )
    n = len(top_specs)
    valid_keys = ','.join(SPECIALTY_META.keys())

    return f"""You are a medical career counselor advising an Egyptian medical graduate at Alexandria Faculty of Medicine.

STUDENT: {student_name} | Rank {student_rank}/{total_students} (top {round(student_rank/total_students*100)}%)

THEIR 20 ANSWERS:
{chr(10).join(lines)}

ALGORITHM TOP {n} SPECIALTIES:
{top_text}

Return ONLY valid JSON (no markdown, no extra text):
{{
  "overall_profile": "2-3 sentences about this student's core medical personality — be specific to their actual answers",
  "key_strength": "The single most defining quality for their career, from their answers",
  "honest_advice": "One frank, constructive piece of advice about a challenge or blind spot",
  "specialties": [
    {{
      "key": "<one of: {valid_keys}>",
      "why_it_fits": "2-3 sentences WHY their specific answers point to this specialty",
      "daily_reality": "One honest sentence about what daily life actually looks like here",
      "watch_out": "One potential challenge or mismatch with this student's profile"
    }}
  ]
}}
Include all {n} specialties in the same order. Reference actual answers. Pure JSON only."""

def generate_local_analysis(student_name, student_rank, total_students, answers, top_specs):
    """Pure-Python analysis — zero API calls, always works."""

    a = answers
    work_pref  = a.get('q1',  '')
    hands_on   = a.get('q2',  '')
    pt_style   = a.get('q3',  '')
    wlb        = a.get('q4',  '')
    stress     = a.get('q13', '')
    emotions   = a.get('q11', '')
    motivation = a.get('q12', '')
    personality= a.get('q19', '')
    vision15   = a.get('q14', '')
    percentile = round(student_rank / total_students * 100)

    # ── Overall profile ──
    work_desc = {
        'a': 'naturally drawn to hands-on procedural and operative medicine',
        'b': 'most energized in clinic, building relationships and reasoning through complex cases',
        'c': 'at their best in analytical, image-based, or laboratory environments',
        'd': 'wired for the fast-paced, high-stakes world of emergency and critical care',
    }.get(work_pref, 'versatile across clinical settings')

    pers_desc = {
        'a': 'The Doer — action-oriented and decisive',
        'b': 'The Thinker — analytical and methodical',
        'c': 'The Nurturer — empathetic and people-driven',
        'd': 'The Observer — detail-focused and systematic',
    }.get(personality, 'a balanced clinician')

    motiv_desc = {
        'a': 'driven by immediate, visible results',
        'b': 'motivated by solving complex diagnostic puzzles',
        'c': 'passionate about advancing medical knowledge through research',
        'd': 'fulfilled by supporting vulnerable patients through their hardest moments',
    }.get(motivation, 'motivated by clinical excellence')

    pt_desc = {
        'b': 'long-term patient relationships',
        'c': 'focused, minimal-contact analytical work',
        'a': 'focused, time-limited patient encounters',
    }.get(pt_style, 'a variety of patient interactions')

    overall_profile = (
        f"{student_name} is {work_desc}, with a personality profile of {pers_desc}. "
        f"They are {motiv_desc}, and prefer {pt_desc}. "
        f"At rank {student_rank} of {total_students} (top {percentile}%), "
        f"they have {'strong access to competitive specialties' if percentile <= 30 else 'good options across a broad range of specialties'}."
    )

    # ── Key strength ──
    key_strength = {
        'a': "decisive action and technical execution under pressure — a natural fit for procedural and operative medicine",
        'b': "methodical clinical reasoning and diagnostic acuity — the ability to work through complexity systematically",
        'c': "deep empathy and genuine patient connection — patients will feel truly heard and cared for",
        'd': "meticulous attention to detail and systematic analysis — nothing slips through the cracks",
    }.get(personality, "clinical versatility and adaptability across settings")

    # ── Honest advice ──
    top_key = top_specs[0][0] if top_specs else ''
    surgical_specs  = {'surgery','cardiac_surg','ortho','neurosurg','plastic','ophth','urology','ent','obgyn'}
    demanding_specs = {'surgery','cardiac_surg','neurosurg','emergency','anesth'}
    heavy_specs     = {'oncology','peds','emergency'}

    if wlb == 'a' and top_key in demanding_specs:
        honest_advice = (
            "Your top specialty involves demanding hours and frequent on-call that conflict with your "
            "stated need for work-life balance. Be honest with yourself about this trade-off before "
            "committing — or explore its more outpatient-focused subspecialties."
        )
    elif hands_on == 'c' and top_key in surgical_specs:
        honest_advice = (
            "Your answers favor intellectual reasoning over manual procedures, yet your scores point "
            "toward surgical fields. Explore whether a diagnostic specialty like radiology, neurology, "
            "or internal medicine might be a better daily-life fit."
        )
    elif stress == 'b' and top_key in {'emergency','anesth','cardiac_surg','neurosurg'}:
        honest_advice = (
            "You perform best in calm, controlled environments — yet your top match is a high-acuity "
            "field where daily crises are the norm. Ask yourself whether you're drawn to the idea of "
            "this specialty, or its actual day-to-day reality."
        )
    elif emotions == 'c' and top_key in heavy_specs:
        honest_advice = (
            "You prefer limiting emotionally heavy cases, but your top specialty regularly involves "
            "end-of-life discussions or critically ill patients. Building emotional resilience tools "
            "early in your career will be essential if you pursue this path."
        )
    elif vision15 == 'c' and top_key not in {'pathology','clinical_path','radiology','internal'}:
        honest_advice = (
            "You see yourself as an academic in 15 years — make sure you choose a department with "
            "active research output, and start pursuing publications from day one of residency."
        )
    elif percentile > 60:
        honest_advice = (
            "Your rank gives access to a good range of specialties, but the most competitive fields "
            "will require a solid backup plan. Define a clear first choice and a realistic second "
            "option before matching day."
        )
    else:
        honest_advice = (
            "Your interest profile aligns well with your top specialties. Confirm your choice through "
            "direct clinical exposure before the match, and speak to current residents in your "
            "preferred field about the day-to-day reality."
        )

    # ── Per-specialty insights ──
    INSIGHTS = {
        'internal':     ("Rewards those who love building the full clinical picture before acting — your reasoning-first style is a direct asset here.",
                         "Ward rounds, complex polypharmacy, multidisciplinary consults, and long-term outpatient follow-up.",
                         "Without a clear subspecialty plan, the breadth of internal medicine can feel overwhelming over time."),
        'surgery':      ("Action-oriented and technically driven — surgery rewards those who want to fix problems decisively with their hands.",
                         "Early mornings, long OR days, post-op rounds, and frequent on-call; physical and mental endurance are non-negotiable.",
                         "Private life takes a real hit during residency and early career; confirm you're genuinely willing to pay that cost."),
        'cardiology':   ("Blends procedural excitement with deep clinical reasoning — ideal for someone who wants both intellectual challenge and hands-on skill.",
                         "Echo rounds, cath lab procedures, CCU management, and outpatient clinic — high variety and high stakes.",
                         "Highly competitive; strong academic credentials and research output are expected to stand out."),
        'cardiac_surg': ("Demands near-perfect technical skill under extreme pressure — for those who want the pinnacle of surgical intensity.",
                         "Long, physically demanding operations followed by ICU rounds; brutal hours but extraordinary outcomes.",
                         "One of the most sacrificial training paths in medicine; personal life will be largely on hold for years."),
        'peds':         ("Matches a drive to care for vulnerable patients — children's resilience and recovery make the difficult moments worthwhile.",
                         "Busy inpatient wards, outpatient developmental reviews, vaccinations, and the emotional complexity of anxious parents.",
                         "Communicating with worried families under stress requires a specific emotional skill set that takes time to develop."),
        'obgyn':        ("Suits those who want a blend of surgical procedures, longitudinal care, and high-stakes acute moments — rarely boring.",
                         "Deliveries at all hours, surgical lists, antenatal clinic, and gynecology emergencies — high variety and adrenaline.",
                         "Labor's unpredictability means your schedule is rarely truly off; night calls are frequent and unavoidable."),
        'radiology':    ("If visual pattern recognition excites you and you prefer a quieter consultation model, radiology offers one of the best quality-of-life profiles in medicine.",
                         "Reporting CT/MRI/X-rays, performing guided biopsies and interventional procedures, and consulting from the reading room.",
                         "Limited direct patient contact — confirm you're comfortable being 'behind the scenes' long-term before committing."),
        'pathology':    ("Suits The Observer — methodical, detail-oriented, and comfortable working independently without daily patient pressure.",
                         "Microscope-based tissue analysis, issuing diagnostic reports, and supporting clinical teams with expert lab interpretation.",
                         "Can feel isolated from clinical medicine; if you miss patient contact later in your career, switching out is difficult."),
        'clinical_path':("Connects lab science with direct clinical impact — interpreting bloodwork, running transfusion medicine, supporting diagnostics.",
                         "Laboratory management, quality control, haematology reports, and responding to clinical queries from wards.",
                         "Less procedural than other fields; if you crave hands-on work, this may feel limiting over a long career."),
        'neurology':    ("The ultimate intellectual specialty — complex presentations, precise localization, and long-term relationships with fascinating patients.",
                         "Outpatient epilepsy and Parkinson's clinics, acute stroke calls, and detailed neurological examinations.",
                         "Progress in neurological disease is often slow; if you need quick visible results to stay motivated, that can become draining."),
        'neurosurg':    ("For the technically elite who thrive under extreme pressure — the combination of surgical precision and high-stakes urgency is unique to this field.",
                         "Brain tumor resections, spine surgeries, emergency bleeds, and ICU management of critically ill neurological patients.",
                         "One of the longest and most demanding training paths in medicine; your commitment must be absolute from day one."),
        'emergency':    ("Built for Doers who thrive in chaos — rapid decisions, wildly varied presentations, and immediate feedback on every single case.",
                         "Resuscitations, trauma calls, medical emergencies, and a waiting room that never empties; no two shifts are the same.",
                         "Shift work and witnessing suffering without long-term follow-up can cause burnout without strong coping strategies in place."),
        'anesth':       ("Combines technical precision with critical care thinking — perfect for those who want procedural mastery and a key role in every operation.",
                         "Pre-op assessment, intraoperative management, post-op recovery, and intensive care — technically demanding and fast-paced.",
                         "You're largely invisible to patients who are asleep; if recognition and direct relationships matter to you, that gap can be frustrating."),
        'derm':         ("Offers outstanding work-life balance with procedural variety — a smart choice for those who value quality of life without sacrificing clinical interest.",
                         "Clinic-based consultations, minor surgical procedures, laser treatments, and the diagnostic satisfaction of visual pattern recognition.",
                         "Extremely competitive for residency spots; getting in usually requires top academic standing and strong faculty relationships."),
        'ortho':        ("Suits the hands-on Doer who wants immediate, tangible results — watching a patient walk again after surgery is deeply rewarding.",
                         "Fracture reductions, joint replacements, arthroscopy, and sports injury clinic — physically demanding for surgeon and patient alike.",
                         "The training culture in orthopedics can be tough; resilience and a thick skin are necessary traits to develop early."),
        'ophth':        ("Combines microsurgical precision with outstanding outcomes — restoring someone's vision is one of medicine's most rewarding interventions.",
                         "Cataract surgery, retinal procedures, outpatient refractions, and laser treatments in a mostly predictable and clean environment.",
                         "Highly competitive and technically demanding; fine motor precision is essential — shaky hands are a genuine limiting factor."),
        'ent':          ("Blends surgical procedures with clinic-based management and a genuinely good lifestyle — a well-rounded choice for those who want variety.",
                         "Tonsillectomies, endoscopies, hearing evaluations, head-and-neck cases, and busy outpatient clinics.",
                         "The surgical cases, while satisfying, are rarely life-or-death; if high-stakes drama is your motivator, that can feel underwhelming."),
        'plastic':      ("Combines elite technical artistry with extraordinary patient outcomes — reconstructive work carries deep meaning far beyond aesthetics.",
                         "Reconstructive flaps, burns management, aesthetic procedures, and complex hand surgery — an incredibly diverse surgical skill set.",
                         "One of the most competitive pathways; the private practice dream often takes 10+ years post-residency to fully materialize."),
        'urology':      ("An underrated blend of surgery and medicine with a relatively good lifestyle for a surgical specialty — and growing fast with robotic technology.",
                         "Endoscopic procedures, robotic surgery, outpatient stone management, and oncology follow-up — high variety and ongoing innovation.",
                         "Less public prestige than cardiac or neuro surgery; confirm the day-to-day work genuinely excites you beyond the name."),
        'rheum':        ("Rewards those who enjoy long-term relationships and intellectual complexity — autoimmune disease is never straightforward and always evolving.",
                         "Chronic disease management, joint injections, immunosuppression monitoring, and detective-style diagnostic workups.",
                         "Progress is slow and patients rarely fully 'cure' — if you need rapid, visible wins to stay motivated, this will test your patience."),
        'pulm':         ("Suits those who enjoy both acute and chronic care — from ICU ventilator management to long-term COPD and asthma outpatient clinics.",
                         "Bronchoscopy, sleep studies, outpatient spirometry, and ICU rotations — a good blend of technology and ongoing patient relationships.",
                         "End-stage respiratory disease carries a heavy palliative burden; emotional resilience is critical to avoid compassion fatigue."),
        'oncology':     ("Attracts those with emotional resilience and a deep motivation to make a difference — profound meaning despite the difficulty of the work.",
                         "Chemotherapy protocols, tumor board discussions, clinical trial enrollment, and honest end-of-life conversations.",
                         "Emotional burnout is a genuine risk; you will form bonds with patients who don't always survive, and that weight accumulates over a career."),
    }

    default_insight = (
        'Your quiz answers align with this specialty based on your stated interests and work-style preferences.',
        'A full mix of inpatient, outpatient, and on-call responsibilities typical of this field.',
        'Confirm your interest with direct clinical exposure during rotations before committing fully.',
    )

    specialties_out = []
    for spec_key, _ in top_specs:
        why, daily, watch = INSIGHTS.get(spec_key, default_insight)
        specialties_out.append({
            'key':           spec_key,
            'why_it_fits':   why,
            'daily_reality': daily,
            'watch_out':     watch,
        })

    return {
        'overall_profile': overall_profile,
        'key_strength':    key_strength,
        'honest_advice':   honest_advice,
        'specialties':     specialties_out,
    }


def call_groq_analysis(student_name, student_rank, total_students, answers, top_specs):
    if not GROQ_API_KEY:
        return None, "GROQ_API_KEY is not set in environment variables."
    try:
        prompt = build_groq_prompt(student_name, student_rank, total_students, answers, top_specs)
        resp = requests.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 2500, "temperature": 0.4},
            timeout=35,
        )
        resp_json = resp.json()
        # Surface API-level errors (wrong model, bad key, quota, etc.)
        if resp.status_code != 200 or "error" in resp_json:
            api_err = resp_json.get("error", {})
            msg = api_err.get("message", str(resp_json)) if isinstance(api_err, dict) else str(api_err)
            return None, f"Groq API error {resp.status_code}: {msg}"
        raw = resp_json["choices"][0]["message"]["content"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip()), None
    except requests.exceptions.Timeout:
        return None, "Request timed out after 35 seconds — Groq did not respond in time."
    except requests.exceptions.ConnectionError as e:
        return None, f"Connection error reaching Groq: {e}"
    except json.JSONDecodeError as e:
        return None, f"Groq returned non-JSON response: {e}"
    except Exception as e:
        return None, f"Unexpected error: {type(e).__name__}: {e}"

@app.route('/residency/specialty', methods=['GET', 'POST'])
def specialty_quiz():
    result_data = student_name = student_rank = student_id = error = None

    if request.method == 'POST':
        try:
            student_id = request.form.get('student_id', '').strip()
            answers    = {f'q{i}': request.form.get(f'q{i}')
                          for i in range(1, 21) if request.form.get(f'q{i}')}

            if not student_id:
                error = 'Please enter your student ID to continue.'
            elif len(answers) < 20:
                error = f'Please answer all 20 questions. You answered {len(answers)}/20.'
            else:
                match = sheet1_df[sheet1_df['ID'].astype(str) == student_id]
                if match.empty:
                    error = f'Student ID "{student_id}" not found. Please check the number.'
                else:
                    row          = match.iloc[0]
                    student_name = str(row.get('NAME', 'Unknown'))
                    total        = row.get('TOTAL')
                    if pd.isna(total):
                        error = 'Cannot determine rank — TOTAL score is missing.'
                    else:
                        total_scores   = sheet1_df['TOTAL'].dropna()
                        student_rank   = int((total_scores > total).sum()) + 1
                        total_students = int(len(total_scores))

                        post_preds, nopost_preds = get_residency_predictions(
                            student_rank, residency_24_df, residency_25_df)

                        interest = compute_specialty_scores(answers)
                        combined = {}
                        for sk, ip in interest.items():
                            av = get_availability_for_spec(post_preds, nopost_preds, sk)
                            combined[sk] = {'interest': int(ip), 'availability': int(av),
                                            'combined': int(round(ip * 0.65 + av * 0.35))}

                        top_specs   = sorted(combined.items(),
                                             key=lambda x: x[1]['combined'], reverse=True)[:8]
                        ai_analysis = generate_local_analysis(student_name, student_rank,
                                                              total_students, answers, top_specs)

                        ai_by_key = {}
                        if ai_analysis and 'specialties' in ai_analysis:
                            for s in ai_analysis['specialties']:
                                ai_by_key[s.get('key', '')] = s

                        result_data = {
                            'top_specs':      top_specs,
                            'total_students': total_students,
                            'ai_profile':     (ai_analysis or {}).get('overall_profile', ''),
                            'ai_strength':    (ai_analysis or {}).get('key_strength', ''),
                            'ai_advice':      (ai_analysis or {}).get('honest_advice', ''),
                            'ai_by_key':      ai_by_key,
                            'ai_ok':          True,
                            'ai_error':       None,
                        }
        except Exception as _e:
            import traceback
            error = 'Internal error: ' + type(_e).__name__ + ': ' + str(_e) + chr(10) + chr(10) + traceback.format_exc()

    return render_template_string(
        specialty_quiz_template,
        questions=QUIZ_QUESTIONS, result_data=result_data,
        student_name=student_name, student_rank=student_rank,
        student_id=student_id, error=error, specialty_meta=SPECIALTY_META,
    )

specialty_quiz_template = """<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>What Is My Specialty?</title>
<link rel="icon" type="image/png" href="{{ url_for('static', filename='logoTB.png') }}">
<style>
:root{--primary:#667eea;--secondary:#764ba2;--green:#27ae60;--bg:#f0f4f8;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:Arial,sans-serif;background:var(--bg);min-height:100vh;}
body::before{content:"";background-image:url('https://i.ibb.co/zHRhsP6j');background-size:cover;background-position:center;opacity:.06;top:0;left:0;bottom:0;right:0;position:fixed;z-index:-1;}
.wrap{max-width:950px;margin:0 auto;padding:28px 18px;}
/* HEADER */
.hdr{display:flex;align-items:center;justify-content:center;gap:18px;margin-bottom:22px;}
.hdr img{height:62px;opacity:.85;}
.hdr h1{font-size:26px;font-weight:900;background:linear-gradient(135deg,var(--primary),var(--secondary));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hdr p{font-size:13px;font-weight:bold;font-style:italic;background:linear-gradient(45deg,#ff6b6b,#4ecdc4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.hdr a{text-decoration:none;}
/* NAV */
.nav{display:flex;justify-content:center;gap:9px;margin-bottom:24px;flex-wrap:wrap;}
.nb{padding:10px 18px;font-size:13px;font-weight:bold;border-radius:25px;text-decoration:none;color:white;box-shadow:0 4px 12px rgba(0,0,0,.18);transition:transform .2s;white-space:nowrap;}
.nb:hover{transform:translateY(-2px);}
.nb.home{background:linear-gradient(45deg,var(--primary),var(--secondary));}
.nb.y24{background:linear-gradient(45deg,#ff6b6b,#ee5a52);}
.nb.y25{background:linear-gradient(45deg,#4ecdc4,#44a08d);}
.nb.pred{background:linear-gradient(45deg,#f39c12,#8e44ad);}
.nb.act{background:linear-gradient(45deg,#1a1a2e,#16213e);}
/* ERROR */
.err{background:#fde8e8;border:1px solid #f5c6c6;border-radius:12px;padding:16px;color:#c0392b;font-size:15px;font-weight:bold;margin-bottom:18px;text-align:center;}
/* ID CARD */
.id-card{background:white;border-radius:20px;padding:36px 28px 30px;box-shadow:0 8px 28px rgba(0,0,0,.1);margin-bottom:22px;text-align:center;}
.id-card .ico{font-size:44px;margin-bottom:10px;}
.id-card h2{font-size:26px;font-weight:900;margin-bottom:8px;background:linear-gradient(135deg,var(--primary),var(--secondary));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.id-card p{color:#666;margin-bottom:22px;font-size:14px;line-height:1.65;}
.id-row{display:flex;justify-content:center;align-items:center;gap:10px;flex-wrap:wrap;}
.id-row input{font-size:17px;padding:12px 20px;width:260px;border:2px solid #ddd;border-radius:30px;outline:none;transition:all .3s;text-align:center;}
.id-row input:focus{border-color:var(--primary);box-shadow:0 0 10px rgba(102,126,234,.3);}
.id-row button{font-size:15px;padding:12px 26px;border-radius:30px;border:none;cursor:pointer;background:linear-gradient(45deg,var(--primary),var(--secondary));color:white;font-weight:bold;box-shadow:0 4px 14px rgba(102,126,234,.4);transition:all .3s;}
.id-row button:hover{transform:translateY(-2px);}
.feats{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:18px;}
.feat{background:#f8f8ff;border:1px solid #e0e0ff;border-radius:10px;padding:7px 14px;font-size:13px;color:#555;}
/* PROGRESS */
.prog-wrap{background:white;border-radius:16px;padding:16px 22px;box-shadow:0 4px 14px rgba(0,0,0,.08);margin-bottom:20px;}
.prog-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px;}
.prog-title{font-size:14px;font-weight:bold;color:#333;}
.prog-ct{font-size:13px;color:#888;}
.prog-bg{height:10px;background:#e8e8e8;border-radius:5px;overflow:hidden;}
.prog-fill{height:100%;border-radius:5px;transition:width .5s;background:linear-gradient(90deg,var(--primary),var(--secondary));}
.dots{display:flex;gap:8px;margin-top:11px;justify-content:center;}
.dot{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:bold;cursor:pointer;transition:all .3s;border:2px solid #ddd;background:#f8f8f8;color:#999;}
.dot.done{background:var(--green);border-color:var(--green);color:white;}
.dot.active{background:linear-gradient(135deg,var(--primary),var(--secondary));border-color:var(--primary);color:white;box-shadow:0 3px 10px rgba(102,126,234,.4);}
/* SECTION */
.sec-panel{display:none;}
.sec-panel.on{display:block;}
.sec-lbl{text-align:center;margin-bottom:20px;}
.sec-lbl .si{font-size:28px;}
.sec-lbl .sn{font-size:21px;font-weight:900;display:block;margin-top:4px;background:linear-gradient(135deg,var(--primary),var(--secondary));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.sec-lbl .sd{font-size:13px;color:#888;margin-top:3px;}
/* Q CARD */
.qc{background:white;border-radius:16px;padding:20px 24px;box-shadow:0 4px 16px rgba(0,0,0,.08);margin-bottom:14px;border-left:5px solid var(--primary);transition:border-color .3s;}
.qc.ans{border-left-color:var(--green);}
.qnum{font-size:11px;color:var(--primary);font-weight:bold;margin-bottom:5px;text-transform:uppercase;letter-spacing:.5px;}
.qtxt{font-size:16px;font-weight:700;color:#1a1a2e;margin-bottom:14px;line-height:1.5;}
.opts{display:flex;flex-direction:column;gap:8px;}
.opt{display:flex;align-items:flex-start;gap:11px;padding:12px 14px;border:2px solid #eee;border-radius:11px;cursor:pointer;transition:all .2s;}
.opt:hover{border-color:var(--primary);background:#f5f5ff;}
.opt input[type=radio]{display:none;}
.opt .mk{width:21px;height:21px;min-width:21px;border-radius:50%;border:2px solid #ccc;display:flex;align-items:center;justify-content:center;margin-top:1px;transition:all .2s;}
.opt .ot{font-size:14px;color:#444;line-height:1.45;}
.opt.sel{border-color:var(--primary);background:linear-gradient(135deg,#f0f0ff,#f8f0ff);}
.opt.sel .mk{background:var(--primary);border-color:var(--primary);}
.opt.sel .mk::after{content:'✓';color:white;font-size:12px;font-weight:bold;}
.opt.sel .ot{color:#222;font-weight:600;}
/* QUIZ NAV */
.qnav{display:flex;justify-content:space-between;margin-top:22px;gap:10px;}
.qnav button{padding:12px 28px;border:none;border-radius:25px;font-size:15px;font-weight:bold;cursor:pointer;transition:all .3s;}
.bp{background:#f0f0f0;color:#666;}
.bp:hover{background:#e0e0e0;}
.bn{background:linear-gradient(45deg,var(--primary),var(--secondary));color:white;box-shadow:0 4px 14px rgba(102,126,234,.4);}
.bn:hover{transform:translateY(-2px);}
.bs{background:linear-gradient(45deg,var(--green),#2ecc71);color:white;box-shadow:0 4px 14px rgba(39,174,96,.4);font-size:16px;}
.bs:hover{transform:translateY(-2px);}
/* RESULTS */
.banner{background:linear-gradient(135deg,var(--primary),var(--secondary));color:white;border-radius:16px;padding:20px 26px;margin-bottom:22px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;box-shadow:0 6px 20px rgba(102,126,234,.4);}
.bi .bn2{font-size:23px;font-weight:900;}
.bi .bs2{font-size:13px;opacity:.85;margin-top:3px;}
.rbadge{background:rgba(255,255,255,.22);border-radius:50%;width:78px;height:78px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:900;font-size:25px;border:3px solid rgba(255,255,255,.45);}
.rbadge small{font-size:10px;opacity:.8;}
/* AI PROFILE */
.ai-card{background:linear-gradient(135deg,#1a1a2e,#16213e);color:white;border-radius:18px;padding:24px 28px;margin-bottom:22px;box-shadow:0 8px 28px rgba(0,0,0,.2);}
.ai-top{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap;}
.ai-badge{background:linear-gradient(45deg,#f39c12,#8e44ad);color:white;padding:4px 13px;border-radius:20px;font-size:12px;font-weight:bold;}
.ai-top h3{font-size:17px;font-weight:900;}
.ai-body{font-size:14px;line-height:1.7;opacity:.92;margin-bottom:14px;}
.ai-pills{display:flex;gap:9px;flex-wrap:wrap;}
.ap{padding:8px 15px;border-radius:20px;font-size:13px;font-weight:bold;line-height:1.4;}
.ap.str{background:rgba(46,204,113,.18);color:#2ecc71;border:1px solid rgba(46,204,113,.3);}
.ap.adv{background:rgba(243,156,18,.18);color:#f39c12;border:1px solid rgba(243,156,18,.3);}
/* RESULTS HEADER */
.rh{text-align:center;margin-bottom:20px;}
.rh h2{font-size:25px;font-weight:900;background:linear-gradient(135deg,var(--primary),var(--secondary));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.rh p{color:#666;font-size:14px;margin-top:5px;}
/* LEGEND */
.leg{background:white;border-radius:13px;padding:14px 20px;box-shadow:0 4px 14px rgba(0,0,0,.07);margin-bottom:20px;}
.leg h3{font-size:13px;font-weight:bold;margin-bottom:9px;color:#555;}
.leg-items{display:flex;gap:16px;flex-wrap:wrap;}
.li2{display:flex;align-items:center;gap:6px;font-size:12px;color:#666;}
.ld{width:11px;height:11px;border-radius:3px;flex-shrink:0;}
.ldi{background:linear-gradient(90deg,var(--primary),var(--secondary));}
.lda{background:linear-gradient(90deg,var(--green),#2ecc71);}
.ldc{background:linear-gradient(90deg,#f39c12,#e74c3c);}
/* SPEC GRID */
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:18px;margin-bottom:26px;}
.sc{background:white;border-radius:19px;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,.09);transition:transform .25s,box-shadow .25s;}
.sc:hover{transform:translateY(-4px);box-shadow:0 12px 32px rgba(0,0,0,.13);}
.sc-head{padding:17px 20px 13px;display:flex;align-items:flex-start;justify-content:space-between;gap:10px;}
.sc.r1 .sc-head{border-top:4px solid gold;}
.sc.r2 .sc-head{border-top:4px solid #b0bec5;}
.sc.r3 .sc-head{border-top:4px solid #cd7f32;}
.sc-left{display:flex;align-items:center;gap:12px;}
.se{font-size:30px;}
.sar{font-size:17px;font-weight:900;color:#1a1a2e;direction:rtl;}
.sen{font-size:11px;color:#888;font-style:italic;margin-top:2px;}
.srb{min-width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:15px;color:white;flex-shrink:0;}
.r1 .srb{background:linear-gradient(135deg,#f6d365,#fda085);}
.r2 .srb{background:linear-gradient(135deg,#b0bec5,#78909c);}
.r3 .srb{background:linear-gradient(135deg,#cd7f32,#a0522d);}
.rn .srb{background:linear-gradient(135deg,var(--primary),var(--secondary));}
.sc-scores{padding:0 20px 14px;}
.srow{display:flex;align-items:center;gap:7px;margin-bottom:6px;}
.slbl{font-size:11px;color:#888;font-weight:bold;width:80px;flex-shrink:0;}
.bbg{flex:1;height:7px;background:#eee;border-radius:4px;overflow:hidden;}
.bf{height:100%;border-radius:4px;transition:width 1s;}
.fi{background:linear-gradient(90deg,var(--primary),var(--secondary));}
.fa{background:linear-gradient(90deg,var(--green),#2ecc71);}
.fc{background:linear-gradient(90deg,#f39c12,#e74c3c);}
.sv{font-size:12px;font-weight:bold;width:30px;text-align:right;}
.vi{color:var(--primary);} .va{color:var(--green);} .vc{color:#e67e22;font-size:13px;font-weight:900;}
/* AI INSIGHT */
.ains{background:linear-gradient(135deg,#f8f0ff,#f0f4ff);border-top:1px solid #e8e0ff;padding:13px 20px 16px;}
.ail{font-size:11px;font-weight:bold;color:#8e44ad;text-transform:uppercase;letter-spacing:.5px;margin-bottom:7px;}
.aiy{font-size:13px;color:#333;line-height:1.55;margin-bottom:7px;}
.aid{font-size:12px;color:#555;line-height:1.5;padding:7px 11px;background:rgba(102,126,234,.07);border-radius:8px;margin-bottom:6px;}
.aiw{font-size:12px;color:#c0392b;line-height:1.5;padding:7px 11px;background:rgba(231,76,60,.06);border-radius:8px;border-left:3px solid #e74c3c;}
/* FOOTER */
.acts{display:flex;gap:10px;justify-content:center;margin-bottom:26px;flex-wrap:wrap;}
.fp{margin-top:28px;padding:15px;border-radius:12px;background:linear-gradient(to right,black,white,green,red);color:white;font-size:20px;font-weight:bold;text-align:center;text-shadow:1px 1px 2px black;}
@media(max-width:640px){
  .qnav{flex-direction:column;}
  .qnav button{width:100%;}
  .sgrid{grid-template-columns:1fr;}
  .id-row input{width:220px;}
}
</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
  <img src="https://i.postimg.cc/0rHzBdbx/8.jpg" alt="Logo">
  <div>
    <h1><a href="/">AFM 26 Results &amp; Analysis</a></h1>
    <p><a href="https://t.me/Abdo_Hamdi6" target="_blank">By : Abdo Hamdy Aly</a></p>
  </div>
</div>

<div class="nav">
  <a href="/"                    class="nb home">🏠 الرئيسية</a>
  <a href="/residency?year=2025" class="nb y25">🏥 2025</a>
  <a href="/residency?year=2024" class="nb y24">🏥 2024</a>
  <a href="/residency/predict"   class="nb pred">📊 Prediction</a>
  <a href="/residency/specialty" class="nb act">🧭 What Is My Specialty?</a>
</div>

{% if error %}<div class="err">⚠️ {{ error }}</div>{% endif %}

{% if result_data %}
<div class="banner">
  <div class="bi">
    <div class="bn2">{{ student_name }}</div>
    <div class="bs2">ID: {{ student_id }} &nbsp;·&nbsp; Rank {{ student_rank }} of {{ result_data.total_students }}</div>
  </div>
  <div class="rbadge">{{ student_rank }}<small>Rank</small></div>
</div>

{% if result_data.ai_ok %}
<div class="ai-card">
  <div class="ai-top">
    <span class="ai-badge">🧭 Personality Analysis</span>
    <h3>Your Medical Personality Profile</h3>
  </div>
  <p class="ai-body">{{ result_data.ai_profile }}</p>
  <div class="ai-pills">
    <div class="ap str">💪 {{ result_data.ai_strength }}</div>
    <div class="ap adv">💡 {{ result_data.ai_advice }}</div>
  </div>
</div>
{% elif result_data.ai_error %}
<div style="background:#fff0f0;border:1px solid #f5c6c6;border-radius:10px;padding:16px 20px;margin:16px 0;text-align:left;direction:ltr;">
  <strong style="color:#c0392b;">⚠️ AI Analysis Failed</strong>
  <pre style="margin:8px 0 0;font-size:13px;color:#555;white-space:pre-wrap;word-break:break-word;">{{ result_data.ai_error }}</pre>
</div>
{% endif %}

<div class="rh">
  <h2>🧭 Your Best-Fit Specialties</h2>
  <p>Ranked by combined Interest Match + Realistic Availability based on your rank</p>
</div>

<div class="leg">
  <h3>📖 Reading the cards:</h3>
  <div class="leg-items">
    <div class="li2"><div class="ld ldi"></div>Interest Match — how strongly your answers align with this specialty</div>
    <div class="li2"><div class="ld lda"></div>Rank Availability — probability based on your rank (historical data)</div>
    <div class="li2"><div class="ld ldc"></div>Combined Score — 65% interest + 35% availability</div>
  </div>
</div>

<div class="sgrid">
{% for rank_idx, (spec_key, scores) in enumerate(result_data.top_specs) %}
{% set meta = specialty_meta[spec_key] %}
{% set rc = 'r1' if rank_idx==0 else ('r2' if rank_idx==1 else ('r3' if rank_idx==2 else 'rn')) %}
{% set ai = result_data.ai_by_key.get(spec_key, {}) %}
<div class="sc {{ rc }}">
  <div class="sc-head">
    <div class="sc-left">
      <span class="se">{{ meta[1] }}</span>
      <div><div class="sar">{{ meta[0] }}</div><div class="sen">{{ meta[2] }}</div></div>
    </div>
    <div class="srb">{{ rank_idx+1 }}</div>
  </div>
  <div class="sc-scores">
    <div class="srow"><span class="slbl">🎯 Interest</span><div class="bbg"><div class="bf fi" style="width:{{ scores.interest }}%"></div></div><span class="sv vi">{{ scores.interest }}%</span></div>
    <div class="srow"><span class="slbl">📊 Availability</span><div class="bbg"><div class="bf fa" style="width:{{ scores.availability }}%"></div></div><span class="sv va">{{ scores.availability }}%</span></div>
    <div class="srow"><span class="slbl">⭐ Combined</span><div class="bbg"><div class="bf fc" style="width:{{ scores.combined }}%"></div></div><span class="sv vc">{{ scores.combined }}%</span></div>
  </div>
  {% if ai %}
  <div class="ains">
    <div class="ail">🤖 AI Insight</div>
    <div class="aiy">{{ ai.get('why_it_fits','') }}</div>
    <div class="aid">📅 {{ ai.get('daily_reality','') }}</div>
    <div class="aiw">⚠️ {{ ai.get('watch_out','') }}</div>
  </div>
  {% endif %}
</div>
{% endfor %}
</div>

<div class="acts">
  <a href="/residency/specialty" class="nb pred">🔄 Retake Quiz</a>
  <a href="/residency/predict"   class="nb pred">📊 Full Residency Prediction</a>
</div>

{% else %}
<div class="id-card">
  <div class="ico">🧭</div>
  <h2>What Is My Specialty?</h2>
  <p>Answer 20 carefully designed questions about your work style, clinical interests,<br>
     personality, and career values. The scoring algorithm will find your best specialty matches — calibrated to your actual residency rank.</p>
  <div class="id-row">
    <input type="text" id="sid" placeholder="Enter Student ID" autocomplete="off" value="{{ student_id or '' }}">
    <button onclick="startQuiz()">🚀 Start Quiz</button>
  </div>
  <div class="feats">
    <span class="feat">📋 20 Questions</span>
    <span class="feat">🤖 GPT-OSS 120B Analysis</span>
    <span class="feat">📊 Rank-Calibrated Results</span>
    <span class="feat">⏱️ ~5 minutes</span>
  </div>
</div>

<form id="qf" method="POST" action="/residency/specialty" style="display:none;">
  <input type="hidden" name="student_id" id="hsid">
  <div class="prog-wrap">
    <div class="prog-hdr">
      <span class="prog-title" id="ptitle">⚙️ Section 1 of 4: Work Style</span>
      <span class="prog-ct"   id="pcount">Questions 1–5 of 20</span>
    </div>
    <div class="prog-bg"><div class="prog-fill" id="pfill" style="width:0%"></div></div>
    <div class="dots">
      <div class="dot active" id="d1" onclick="jump(1)">1</div>
      <div class="dot"        id="d2" onclick="jump(2)">2</div>
      <div class="dot"        id="d3" onclick="jump(3)">3</div>
      <div class="dot"        id="d4" onclick="jump(4)">4</div>
    </div>
  </div>

  {% set secs=[
    ('Work Style',        '⚙️','How you prefer to work day-to-day',           [0,1,2,3,4]),
    ('Clinical Interests','🩺','What excites you clinically',                  [5,6,7,8,9]),
    ('Personality',       '💛','Your values, fears, and motivations',          [10,11,12,13,14]),
    ('Scenarios & Goals', '🚀','Self-knowledge through real-life scenarios',   [15,16,17,18,19]),
  ] %}
  {% for sn,si,sd,qi in secs %}
  {% set s=loop.index %}
  <div class="sec-panel {% if s==1 %}on{% endif %}" id="s{{ s }}">
    <div class="sec-lbl">
      <span class="si">{{ si }}</span>
      <span class="sn">Section {{ s }}: {{ sn }}</span>
      <div class="sd">{{ sd }}</div>
    </div>
    {% for i in qi %}
    {% set q=questions[i] %}
    <div class="qc" id="c_{{ q.id }}">
      <div class="qnum">Question {{ i+1 }} of 20 · {{ q.section }}</div>
      <div class="qtxt">{{ q.text }}</div>
      <div class="opts">
        {% for o in q.options %}
        <label class="opt" id="o_{{ q.id }}_{{ o.id }}" onclick="pick('{{ q.id }}','{{ o.id }}',this)">
          <input type="radio" name="{{ q.id }}" value="{{ o.id }}">
          <div class="mk"></div>
          <div class="ot">{{ o.text }}</div>
        </label>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
    <div class="qnav">
      {% if s>1 %}<button type="button" class="bp" onclick="go({{ s-1 }})">← Previous</button>{% else %}<div></div>{% endif %}
      {% if s<4 %}
      <button type="button" class="bn" onclick="nxt({{ s }})">Next Section →</button>
      {% else %}
      <button type="submit" class="bs" onclick="return sub()">🧭 Reveal My Specialty</button>
      {% endif %}
    </div>
  </div>
  {% endfor %}
</form>
{% endif %}

<div class="fp">🇵🇸 Free Palestine — Gaza Will Be Rebuilt 🇵🇸</div>
</div>
<script>
const SM=[
  {i:'⚙️',n:'Work Style',        r:'Questions 1–5 of 20'},
  {i:'🩺',n:'Clinical Interests', r:'Questions 6–10 of 20'},
  {i:'💛',n:'Personality',        r:'Questions 11–15 of 20'},
  {i:'🚀',n:'Scenarios & Goals',  r:'Questions 16–20 of 20'},
];
const QS=[['q1','q2','q3','q4','q5'],['q6','q7','q8','q9','q10'],
          ['q11','q12','q13','q14','q15'],['q16','q17','q18','q19','q20']];

function startQuiz(){
  const id=document.getElementById('sid').value.trim();
  if(!id){alert('Please enter your Student ID first.');return;}
  document.getElementById('hsid').value=id;
  document.querySelector('.id-card').style.display='none';
  document.getElementById('qf').style.display='block';
  upd(1);
}
function pick(qid,opt,el){
  document.querySelectorAll('[id^="o_'+qid+'_"]').forEach(l=>l.classList.remove('sel'));
  el.classList.add('sel');
  el.querySelector('input[type=radio]').checked=true;
  document.getElementById('c_'+qid)?.classList.add('ans');
}
function upd(sn){
  const m=SM[sn-1];
  document.getElementById('pfill').style.width=((sn-1)/4*100)+'%';
  document.getElementById('ptitle').textContent=m.i+' Section '+sn+' of 4: '+m.n;
  document.getElementById('pcount').textContent=m.r;
  for(let i=1;i<=4;i++){
    const d=document.getElementById('d'+i);
    d.className='dot'+(i<sn?' done':i===sn?' active':'');
  }
}
function nxt(cur){
  for(const qid of QS[cur-1]){
    if(!document.querySelector('input[name="'+qid+'"]:checked')){
      const c=document.getElementById('c_'+qid);
      c.scrollIntoView({behavior:'smooth',block:'center'});
      c.style.boxShadow='0 0 0 3px #e74c3c';
      setTimeout(()=>c.style.boxShadow='',2200);
      alert('Please answer all questions in this section before continuing.');
      return;
    }
  }
  go(cur+1);
}
function go(n){
  document.querySelectorAll('.sec-panel').forEach(p=>p.classList.remove('on'));
  document.getElementById('s'+n).classList.add('on');
  upd(n);
  window.scrollTo({top:0,behavior:'smooth'});
}
function jump(n){
  const cur=[...document.querySelectorAll('.dot')].findIndex(d=>d.classList.contains('active'))+1;
  if(n<=cur)go(n);
}
function sub(){
  for(let s=1;s<=4;s++){
    for(const qid of QS[s-1]){
      if(!document.querySelector('input[name="'+qid+'"]:checked')){
        go(s);
        setTimeout(()=>{
          const c=document.getElementById('c_'+qid);
          c.scrollIntoView({behavior:'smooth',block:'center'});
          c.style.boxShadow='0 0 0 3px #e74c3c';
          setTimeout(()=>c.style.boxShadow='',2200);
        },350);
        alert('Please answer ALL 20 questions before submitting.');
        return false;
      }
    }
  }
  const b=document.querySelector('.bs');
  if(b){b.textContent='\u23f3 Analyzing...';b.disabled=true;b.style.background='linear-gradient(45deg,#888,#aaa)';}

  const form=document.getElementById('qf');
  const data=new FormData(form);
  const ctrl=new AbortController();
  const timer=setTimeout(()=>ctrl.abort(),25000);

  fetch('/residency/specialty',{method:'POST',body:data,signal:ctrl.signal})
    .then(r=>{
      clearTimeout(timer);
      if(!r.ok) throw new Error('Server error: '+r.status+' '+r.statusText);
      return r.text();
    })
    .then(html=>{
      document.open();document.write(html);document.close();
    })
    .catch(err=>{
      clearTimeout(timer);
      if(b){b.textContent='🔄 Try Again';b.disabled=false;b.style.background='linear-gradient(45deg,#e74c3c,#c0392b)';}
      const msg=err.name==='AbortError'
        ?'Request timed out (>25s). Please try again.'
        :'Error: '+err.message+'. Please try again.';
      let box=document.getElementById('sub-err');
      if(!box){box=document.createElement('div');box.id='sub-err';
        box.style.cssText='background:#fff0f0;border:2px solid #e74c3c;border-radius:12px;padding:14px 18px;margin:14px 0;text-align:left;direction:ltr;font-size:14px;color:#c0392b;';
        b.parentNode.insertBefore(box,b);}
      box.textContent=msg;
    });

  return false;
}
window.addEventListener('load',()=>{
  document.querySelectorAll('.bf').forEach(el=>{
    const t=el.style.width;el.style.width='0%';
    setTimeout(()=>el.style.width=t,160);
  });
});
</script>
</body>
</html>"""

if __name__ == '__main__':
    app.run(debug=True)
