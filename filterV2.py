# -*- coding: utf-8 -*-
"""
filterV2.py (담당자 추가 피드백 반영본)
담당자님이 주신 데이터가 xlsx로 변경됨에 따라 xlsx -> xlsx 로 수정
아래 내용들처럼 담당자님이 주신 최저임금 환산 방식 적용 

[最低賃金 환산 방식 - 담당자 지정]
- 日給: 8時間
- 月給: 160時間（8時間×20日）
- 年収/年棒: 1920時間（160時間×12か月）
- 週給: 想定外 → 要確認でOK（환산하지 않음）

[職種判定]
- 지역명/지명형태는 NG
- 모집/급모/고용형태/근무시간/역할/조건 키워드는 要確認
- 시설명은 要確認 (NG 과다 방지)

[출력]
- 審査結果(전체)
- NGのみ
- 要確認のみ
"""

import os
import re
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple

# ============================================================
# 0) 경로
# ============================================================
USER_HOME = os.path.expanduser("~")
DOWNLOADS = os.path.join(USER_HOME, "Downloads")

CSV_NAME = "test_jobdata_0119.xlsx"
CSV_PATH = os.path.join(DOWNLOADS, CSV_NAME)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_XLSX = os.path.join(DOWNLOADS, f"審査結果_JobMasterList_202601051629_{ts}.xlsx")

# ============================================================
# 1) 地域別最低賃金(令和7年度) - 円/時
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
# 2) マニュアル: 허용 고용형태(完全一致)
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
# 3) 담당자 지정 환산값(핵심)
# ============================================================
ASSUME_HOURS_PER_DAY = 8.0
ASSUME_HOURS_PER_MONTH = 160.0   # 8h * 20d
ASSUME_HOURS_PER_YEAR = 1920.0   # 160h * 12m
# WEEK: 想定外 → 要確認 처리

# ============================================================
# 4) 유틸
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
# 5) CSV 로드
# ============================================================
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"CSV 파일이 Downloads에 없습니다: {CSV_PATH}")

df = pd.read_excel(CSV_PATH)

# ============================================================
# 6) 컬럼 고정(이 CSV 헤더 기준)
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
# 7) 체크 함수들
# ============================================================
REQUIRED_COLS_BASE = [
    col_work_company, col_employment, col_job, col_email,
    col_city, col_wage_unit, col_wage_lower
]

def check_required(row):
    missing = []
    for c in REQUIRED_COLS_BASE:
        v = safe_strip(row.get(c))
        if v == "":
            missing.append(c)
    if missing:
        return "NG", "必須項目が空欄: " + ", ".join(missing)
    return "OK", ""

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

def check_employment(row):
    v = safe_strip(row.get(col_employment))
    if v == "":
        return "NG", "雇用形態が空欄"
    if v not in ALLOWED_EMPLOYMENT:
        return "NG", f"雇用形態が許可表記と不一致: {v}"
    return "OK", ""

def check_company_special(row):
    v = safe_strip(row.get(col_work_company))
    if v == "":
        return "NG", "就業先会社名が空欄"
    if any(mark in v for mark in SPECIAL_COMPANY_MARKS):
        return "NG", "就業先会社名に特殊記号(㈱等)を含む"
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

# ---- 職種判定(실무형 완화) ----
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
    v = safe_strip(row.get(col_job))
    if v == "":
        return "NG", "職種が空欄"

    # (A) 地域名 / 地名形式 => NG
    if PREF_RE.search(v):
        return "NG", "職種に地域名(都道府県)が含まれる"
    if looks_like_place(v):
        return "NG", "職種に地名形式(○○区/市/町/村/駅等)が含まれる"

    # (B) 募集・条件・雇用形態・勤務時間・役職 => 要確認
    if any(t in v for t in JOB_CONDITION_TOKENS):
        return "要確認", "職種に募集/雇用形態/勤務時間/役職/条件の混在可能性"

    # (C) 施設名 => 要確認
    if any(t in v for t in FACILITY_TOKENS):
        return "要確認", "職種に施設名が含まれる(表記要確認)"

    return "OK", ""

# ---- 最低賃金 判定(담당자 방식 반영) ----
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
    담당자 지정 환산:
    - HOUR: 그대로
    - DAY: /8
    - MONTH: /160
    - YEAR: /1920
    - WEEK: 想定外 → 要確認(환산하지 않음)
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
# 8) 메인 루프
# ============================================================
rows = []

for _, r in df.iterrows():
    req_s, req_r = check_required(r)
    email_s, email_r = check_email(r)
    emp_s, emp_r = check_employment(r)
    job_s, job_r = check_job_title(r)
    comp_s, comp_r = check_company_special(r)
    priv_s, priv_r = check_private_intro(r)
    city_s, city_r = check_city_garbled(r)

    mw_s, mw_r, mw_pref, mw_minw, mw_hourly, mw_basis = judge_min_wage(r)

    statuses = [req_s, email_s, emp_s, job_s, comp_s, priv_s, city_s, mw_s]
    if "NG" in statuses:
        total = "NG"
    elif "要確認" in statuses:
        total = "要確認"
    else:
        total = "OK"

    reason = " / ".join([x for x in [mw_r, req_r, email_r, emp_r, job_r, comp_r, priv_r, city_r] if x])

    rows.append({
        "判定(総合)": total,
        "理由(要約)": reason,

        "必須項目": req_s,
        "応募先メール": email_s,
        "雇用形態": emp_s,
        "職種": job_s,
        "就業先会社名表記": comp_s,
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
# 9) 저장
# ============================================================
with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
    df_out.to_excel(writer, sheet_name="審査結果", index=False)
    df_out[df_out["判定(総合)"] == "NG"].to_excel(writer, sheet_name="NGのみ", index=False)
    df_out[df_out["判定(総合)"] == "要確認"].to_excel(writer, sheet_name="要確認のみ", index=False)

print("✅ 저장 완료:", OUT_XLSX)
print("✅ 最低賃金: 담당자 지정 환산(8h/160h/1920h), 週給は要確認")
print("✅ 都道府県: GFJ→住所→市区町村→(補助)職種/会社名 で補完")
print("✅ 職種: 地域名/地名形式はNG、条件/施設名は要確認")