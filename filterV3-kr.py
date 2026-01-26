# -*- coding: utf-8 -*-
"""
filterV3.py - 채용공고 자동 필터링 시스템

[담당자 지정 최저임금 환산]
- 日給(일급): 8시간 기준
- 月給(월급): 160시간 (8h×20일)
- 年収(연봉): 1920시간 (160h×12개월)
- 週給(주급): 미정의 → 요확인 처리

[직종 판정 규칙]
- 지역명/지명형태 포함 → NG
- 모집/급모/고용형태/근무시간/역할/조건 → 요확인
- 시설명 → 요확인 (NG 과다 방지)

[출력 파일]
- 審査結果: 전체 심사 결과
- NGのみ: NG만 필터
- 要確認のみ: 요확인만 필터
"""

import os
import re
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple

# ============================================================
# [경로 설정]
# ============================================================
USER_HOME = os.path.expanduser("~")
DOWNLOADS = os.path.join(USER_HOME, "Downloads")

CSV_NAME = "審査データ_20260125分まで.csv"
CSV_PATH = os.path.join(DOWNLOADS, CSV_NAME)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_XLSX = os.path.join(DOWNLOADS, f"Filtered_list_{ts}.xlsx")

# ============================================================
# [최저임금 DB]
# ============================================================
MIN_WAGE = {
    "北海道": 1075, "青森": 1029, "岩手": 1031, "宮城": 1038, "秋田": 1031, "山形": 1032, "福島": 1033,
    "茨城": 1074, "栃木": 1068, "群馬": 1063, "埼玉": 1141, "千葉": 1140, "東京": 1226, "神奈川": 1225,
    "新潟": 1050, "富山": 1062, "石川": 1054, "福井": 1053, "山梨": 1052, "長野": 1061, "岐阜": 1065,
    "静岡": 1097, "愛知": 1140, "三重": 1087, "滋賀": 1080, "京都": 1122, "大阪": 1177, "兵庫": 1116,
    "奈良": 1051, "和歌山": 1045, "鳥取": 1030, "島根": 1033, "岡山": 1047, "広島": 1085, "山口": 1043,
    "徳島": 1046, "香川": 1036, "愛媛": 1033, "高知": 1023, "福岡": 1057, "佐賀": 1030, "長崎": 1031,
    "熊本": 1034, "大分": 1035, "宮崎": 1023, "鹿児島": 1026, "沖縄": 1023,
}
PREF_LIST = list(MIN_WAGE.keys())
PREF_RE = re.compile("|".join(map(re.escape, sorted(PREF_LIST, key=len, reverse=True))))

# ============================================================
# [허용되는 고용형태]
# ============================================================
ALLOWED_EMPLOYMENT = {
    "正社員","契約社員","派遣社員","パート","アルバイト",
    "アルバイト・パート","アルバイト/パート","アルバイト／パート","アルバイト、パート",
    "パート・アルバイト","パート/アルバイト","パート／アルバイト","パート、アルバイト",
    "業務委託",
}

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
SPECIAL_COMPANY_MARKS = ["㈱", "（株）", "(株)", "㈲", "（有）", "(有)"]

# unitText 규칙
UNIT_MAP = {1: "HOUR", 2: "DAY", 3: "MONTH", 4: "YEAR", 5: "WEEK"}

# ============================================================
# [최저임금 환산 상수]
# ============================================================
ASSUME_HOURS_PER_DAY = 8.0
ASSUME_HOURS_PER_MONTH = 160.0   # 8h * 20d
ASSUME_HOURS_PER_YEAR = 1920.0   # 160h * 12m
# WEEK: 想定外 → 要確認 처리

# ============================================================
# [유틸리티 함수]
# ============================================================
def safe_strip(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except:
        pass
    return str(x).strip()

def to_int_safe(x) -> Optional[int]:
    try:
        if x is None or pd.isna(x):
            return None
        return int(float(x))
    except:
        return None

def to_float_safe(x) -> Optional[float]:
    try:
        if x is None or pd.isna(x):
            return None
        return float(x)
    except:
        return None

def has_garbled_text(s: str) -> bool:
    if not isinstance(s, str) or s.strip() == "":
        return False
    if " " in s:
        return True
    if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", s):
        return True
    if re.search(r"闖|驥|伴", s):
        return True
    return False

def find_pref_anywhere(*texts: str) -> Tuple[str, str]:
    for i, t in enumerate(texts, start=1):
        s = safe_strip(t)
        if not s:
            continue
        m = PREF_RE.search(s)
        if m:
            return m.group(0), f"テキスト#{i}から都道府県を抽出"
    return "", "都道府県抽出失敗"

# ============================================================
# [데이터 로드 - CSV 인코딩 자동감지]
# ============================================================
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"❌ CSV 파일 없음: {CSV_PATH}")

# CSV 읽기 - 3가지 인코딩 시도 (utf-8-sig → cp932 → utf-8)
df = None
last_err = None
for enc in ["utf-8-sig", "cp932", "utf-8"]:
    try:
        df = pd.read_csv(CSV_PATH, encoding=enc)
        break
    except Exception as e:
        last_err = e

if df is None:
    raise RuntimeError(f"❌ CSV 읽기 실패: {last_err}")

# ============================================================
# [입력 데이터 컬럼 맵핑]
# ============================================================
col_work_company   = "就業先会社名"
col_intro_company  = "紹介元会社名"
col_email          = "応募先メールアドレス"
col_employment     = "雇用形態"
col_job            = "職種"
col_city           = "市区町村（addressLocality）"
col_pref           = "都道府県（addressRegion）"
col_address        = "勤務地住所"
col_worktime       = "勤務時間/月平均所定労働時間"
col_wage_unit      = "給与形態（unitText）"
col_wage_lower     = "給与下限（minValue）"

# ============================================================
# [데이터 검증 함수 - 9개 체크항목]
# ============================================================
REQUIRED_COLS_BASE = [
    col_work_company, col_employment, col_job, col_email,
    col_city, col_wage_unit, col_wage_lower
]

# 회사명, 고용형태, 직종, 이메일, 시구정촌, 급여형태, 최저임금(급여하한) 확인
def check_required(row):
    missing = []
    for c in REQUIRED_COLS_BASE:
        v = safe_strip(row.get(c))
        if v == "":
            missing.append(c)
    if missing:
        return "NG", "必須項目が空欄: " + ", ".join(missing)
    return "OK", ""

# 정규식으로 메일 형식 검증 (쉼표/세미콜론으로 분리된 복수 메일 지원)
def check_email(row):
    v = safe_strip(row.get(col_email))
    if v == "":
        return "NG", "応募先メールが空欄"

    parts = [p.strip() for p in re.split(r"[,、; \n\r\t]+", v) if p.strip()]
    if not parts:
        return "NG", "応募先メールが空欄"
    for p in parts:
        if not EMAIL_RE.match(p):
            return "NG", f"メール形式不正: {p}"
    return "OK", ""

# 화이트리스트에 있는 고용형태인지 확인
def check_employment(row):
    v = safe_strip(row.get(col_employment))
    if v == "":
        return "NG", "雇用形態が空欄"
    if v not in ALLOWED_EMPLOYMENT:
        return "NG", f"雇用形態が許可表記と不一致: {v}"
    return "OK", ""

def check_company_special(row):
    """[체크 1] 채용처 회사명: 특수기호(㈱) 확인"""
    v = safe_strip(row.get(col_work_company))
    if v == "":
        return "NG", "채용처 회사명 공란"
    if any(mark in v for mark in SPECIAL_COMPANY_MARKS):
        return "NG", "채용처에 특수기호 포함(㈱)"
    return "OK", ""

def check_intro_company_special(row):
    """[체크 2] 소개원 회사명: 특수기호(㈱) 확인"""
    v = safe_strip(row.get(col_intro_company))
    if v == "":
        return "OK", ""  # 공란 허용
    if any(mark in v for mark in SPECIAL_COMPANY_MARKS):
        return "NG", "소개원에 특수기호 포함(㈱)"
    return "OK", ""

def check_private_intro(row):
    work = safe_strip(row.get(col_work_company))
    if work != "非公開":
        return "OK", ""
    intro = safe_strip(row.get(col_intro_company))
    if intro == "":
        return "NG", "就業先会社名が非公開かつ紹介元会社名が空欄"
    emp = safe_strip(row.get(col_employment))
    if emp == "派遣社員":
        return "NG", "就業先会社名が非公開かつ雇用形態が派遣社員"
    return "OK", ""

def check_city_garbled(row):
    v = safe_strip(row.get(col_city))
    if v == "":
        return "NG", "市区町村が空欄"
    if has_garbled_text(v):
        return "NG", "市区町村に文字化けの可能性"
    return "OK", ""

# [체크 4] 직종 판정 - 지역명/지명/모집키워드/숫자 체크
JOB_CONDITION_TOKENS = [
    "募集", "急募", "大募集", "積極採用", "オープニング", "新規",
    "正社員", "契約社員", "派遣社員", "アルバイト", "パート", "業務委託",
    "夜勤", "日勤", "深夜", "早朝", "交替", "シフト", "残業",
    "未経験", "経験不問", "学歴不問", "資格不問", "○○不問", "歓迎", "優遇",
    "高収入", "日払い", "週払い", "即日", "短期", "長期", "寮", "社宅",
    "在宅", "リモート", "テレワーク",
    "マネージャー", "リーダー", "部長", "課長", "係長", "主任", "候補",
]
FACILITY_TOKENS = [
    "病院", "クリニック", "医院", "歯科",
    "学校", "大学", "専門学校", "保育園", "幼稚園",
    "ホテル", "旅館",
    "空港", "センター", "工場", "倉庫", "店舗", "営業所", "本社", "支店",
]
PLACE_INNER_RE = re.compile(r"(区|市|町|村|駅)")

def looks_like_place(s: str) -> bool:
    t = safe_strip(s)
    if len(t) < 3:
        return False
    return bool(PLACE_INNER_RE.search(t))

def check_job_title(row):
    """[체크 4] 직종 검증"""
    v = safe_strip(row.get(col_job))
    if v == "":
        return "NG", "직종 공란"

    # (A) 지역명 포함 → NG
    if PREF_RE.search(v):
        return "NG", "직종에 지역명(도도부현) 포함"
    if looks_like_place(v):
        return "NG", "직종에 지명형식(○○구/시/町/村/역) 포함"

    # (B) 모집/조건/고용형태/근무시간/역할 → 요확인
    if any(t in v for t in JOB_CONDITION_TOKENS):
        return "要確認", "직종에 모집/고용형태/근무시간/역할/조건 혼합 가능"

    # (C) 숫자 포함 → 요확인 (관리번호 등 직종 불관련)
    if re.search(r'\d', v):
        return "要確認", "직종에 숫자 포함(관리번호 가능성)"

    return "OK", ""

# [체크 9] 최저임금 판정 - 도도부현 추출 및 시급 환산
def resolve_pref(row) -> Tuple[str, str]:
    pref_raw = safe_strip(row.get(col_pref))
    if pref_raw in MIN_WAGE:
        return pref_raw, "GFJ都道府県を使用"

    addr = safe_strip(row.get(col_address))
    city = safe_strip(row.get(col_city))
    job  = safe_strip(row.get(col_job))
    comp = safe_strip(row.get(col_work_company))

    pref2, b2 = find_pref_anywhere(addr, city, job, comp)
    if pref2 in MIN_WAGE:
        return pref2, b2

    return "", "都道府県不明(補完失敗)"

def hourly_from_unit(unit_code: int, amount: float):
    """
    [담당자 지정 환산 규칙]
    - HOUR: 그대로 사용
    - DAY: ÷8시간
    - MONTH: ÷160시간 (8h×20일)
    - YEAR: ÷1920시간 (160h×12개월)
    - WEEK: 미정의 → 요확인
    """
    unit = UNIT_MAP.get(unit_code, "UNKNOWN")

    if unit == "HOUR":
        return amount, "HOUR: 下限をそのまま時給として使用"

    if unit == "DAY":
        return amount / ASSUME_HOURS_PER_DAY, f"DAY→時給: {ASSUME_HOURS_PER_DAY}h/日(固定)で換算"

    if unit == "MONTH":
        return amount / ASSUME_HOURS_PER_MONTH, f"MONTH→時給: {ASSUME_HOURS_PER_MONTH}h/月(固定:8h×20d)で換算"

    if unit == "YEAR":
        return amount / ASSUME_HOURS_PER_YEAR, f"YEAR→時給: {ASSUME_HOURS_PER_YEAR}h/年(固定:160h×12m)で換算"

    if unit == "WEEK":
        return None, "WEEK: 想定外(要確認) - 時給換算しない"

    return None, "給与形態(unitText)不明"

def judge_min_wage(row):
    pref, pref_basis = resolve_pref(row)
    unit_code = to_int_safe(row.get(col_wage_unit))
    lower = to_float_safe(row.get(col_wage_lower))

    if pref == "":
        return "NG", "最低賃金判定不可(都道府県不明)", None, None, None, pref_basis

    minw = float(MIN_WAGE[pref])

    if unit_code is None:
        return "NG", "最低賃金判定不可(給与形態unitText不明)", pref, minw, None, pref_basis
    if lower is None:
        return "NG", "最低賃金判定不可(給与下限minValue不明)", pref, minw, None, pref_basis

    hourly, basis = hourly_from_unit(unit_code, lower)

    # WEEK 등 想定外는 要確認으로 처리
    if hourly is None and UNIT_MAP.get(unit_code) == "WEEK":
        return "要確認", "最低賃金要確認(週給は想定外)", pref, minw, None, f"{pref_basis} / {basis}"

    if hourly is None:
        return "NG", "最低賃金判定不可(時給換算不可)", pref, minw, None, f"{pref_basis} / {basis}"

    if hourly >= minw:
        return "OK", "", pref, minw, hourly, f"{pref_basis} / {basis}"

    return "NG", f"最低賃金未満(換算時給{hourly:.2f} < {minw})", pref, minw, hourly, f"{pref_basis} / {basis}"

# ============================================================
# [메인 루프 - 각 행 심사처리]
# ============================================================
rows = []

for _, r in df.iterrows():
    req_s, req_r = check_required(r)
    email_s, email_r = check_email(r)
    emp_s, emp_r = check_employment(r)
    job_s, job_r = check_job_title(r)
    comp_s, comp_r = check_company_special(r)
    intro_s, intro_r = check_intro_company_special(r)  # 紹介元会社名の特殊記号チェック
    priv_s, priv_r = check_private_intro(r)
    city_s, city_r = check_city_garbled(r)

    mw_s, mw_r, mw_pref, mw_minw, mw_hourly, mw_basis = judge_min_wage(r)

    statuses = [req_s, email_s, emp_s, job_s, comp_s, intro_s, priv_s, city_s, mw_s]
    if "NG" in statuses:
        total = "NG"
    elif "要確認" in statuses:
        total = "要確認"
    else:
        total = "OK"

    reason = " / ".join([x for x in [mw_r, req_r, email_r, emp_r, job_r, comp_r, intro_r, priv_r, city_r] if x])

    rows.append({
        "判定(総合)": total,
        "理由(要約)": reason,

        "必須項目": req_s,
        "応募先メール": email_s,
        "雇用形態": emp_s,
        "職種": job_s,
        "就業先会社名表記": comp_s,
        "紹介元会社名表記": intro_s,  # 紹介元会社名の特殊記号チェック結果
        "非公開→紹介元会社名": priv_s,
        "GFJ市区町村": city_s,
        "最低賃金判定": mw_s,

        "最低賃金_都道府県": mw_pref if mw_pref else safe_strip(r.get(col_pref)),
        "最低賃金_基準値(円/時)": mw_minw,
        "給与形態(unitText)": to_int_safe(r.get(col_wage_unit)),
        "給与下限(minValue)": to_float_safe(r.get(col_wage_lower)),
        "時給換算値(円/時)": mw_hourly,
        "最低賃金_換算根拠": mw_basis,

        # 디버그용
        "勤務地住所": safe_strip(r.get(col_address)),
        "市区町村（addressLocality）": safe_strip(r.get(col_city)),
        "勤務時間/月平均所定労働時間": safe_strip(r.get(col_worktime)),
        "職種(原文)": safe_strip(r.get(col_job)),
    })

out = pd.DataFrame(rows)
df_out = pd.concat([out, df], axis=1)

# ============================================================
# [결과 저장 - 3개 시트로 분류]
# ============================================================
with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
    df_out.to_excel(writer, sheet_name="審査結果", index=False)  # 전체 결과
    df_out[df_out["判定(総合)"] == "NG"].to_excel(writer, sheet_name="NGのみ", index=False)  # NG만
    df_out[df_out["判定(総合)"] == "要確認"].to_excel(writer, sheet_name="要確認のみ", index=False)  # 요확인만

print("✅ 처리 완료:", OUT_XLSX)
print("🔹 최저임금: 담당자 환산(일급8h/월160h/연1920h), 주급은 요확인")
print("🔹 도도부현: GFJ → 주소 → 시구정촌 → 직종/회사 순서로 보완")
print("🔹 직종판정: 지역명/지명형식은 NG, 모집/조건/숫자는 요확인")