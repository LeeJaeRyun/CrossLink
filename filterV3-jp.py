# -*- coding: utf-8 -*-
"""
filterV3.py - 求人案件 自動フィルタリング システム

【担当者指定 最低賃金換算】
- 日給: 8時間基準
- 月給: 160時間 (8h×20日)
- 年収: 1920時間 (160h×12ヶ月)
- 週給: 未定義 → 要確認処理

【職種判定ルール】
- 地域名・地名形式を含む → NG
- 募集・雇用形態・勤務時間・役割・条件 → 要確認
- 施設名 → 要確認 (NG過多防止)

【出力ファイル】
- 審査結果: 全体審査結果
- NGのみ: NG項目のみ抽出
- 要確認のみ: 要確認項目のみ抽出
"""

import os
import re
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple

# ============================================================
# 【パス設定】
# ============================================================
USER_HOME = os.path.expanduser("~")
DOWNLOADS = os.path.join(USER_HOME, "Downloads")

CSV_NAME = "ハピリク審査データ.csv"
CSV_PATH = os.path.join(DOWNLOADS, CSV_NAME)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_XLSX = os.path.join(DOWNLOADS, f"審査結果_JobMasterList_202601051629_{ts}.xlsx")

# ============================================================
# 【最低賃金DB - 2025年度】
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
# 【許可する雇用形態 (完全一致)】
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
# 【最低賃金換算定数 (担当者指定)】
# ============================================================
ASSUME_HOURS_PER_DAY = 8.0
ASSUME_HOURS_PER_MONTH = 160.0   # 8h * 20d
ASSUME_HOURS_PER_YEAR = 1920.0   # 160h * 12m
# WEEK: 想定外 → 要確認 처리

# ============================================================
# 【ユーティリティ関数】
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
# 【データ読み込み - CSV エンコーディング自動検出】
# ============================================================
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"❌ CSVファイルなし: {CSV_PATH}")

# CSV読み込み - 3つのエンコーディング試行 (utf-8-sig → cp932 → utf-8)
df = None
last_err = None
for enc in ["utf-8-sig", "cp932", "utf-8"]:
    try:
        df = pd.read_csv(CSV_PATH, encoding=enc)
        break
    except Exception as e:
        last_err = e

if df is None:
    raise RuntimeError(f"❌ CSV読み込み失敗: {last_err}")

# ============================================================
# 【入力データ カラムマッピング】
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
# 【データ検証関数 - 9個のチェック項目】
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
    """【チェック1】採用先会社名: 特殊記号(㈱)確認"""
    v = safe_strip(row.get(col_work_company))
    if v == "":
        return "NG", "採用先会社名が空欄"
    if any(mark in v for mark in SPECIAL_COMPANY_MARKS):
        return "NG", "採用先に特殊記号を含む(㈱)"
    return "OK", ""

def check_intro_company_special(row):
    """【チェック2】紹介元会社名: 特殊記号(㈱)確認"""
    v = safe_strip(row.get(col_intro_company))
    if v == "":
        return "OK", ""  # 空欄を許可
    if any(mark in v for mark in SPECIAL_COMPANY_MARKS):
        return "NG", "紹介元に特殊記号を含む(㈱)"
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

# 【チェック4】職種判定 - 地域名・地名・募集キーワード・数字チェック
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
    """【チェック4】職種検証"""
    v = safe_strip(row.get(col_job))
    if v == "":
        return "NG", "職種が空欄"

    # (A) 地域名を含む → NG
    if PREF_RE.search(v):
        return "NG", "職種に地域名(都道府県)を含む"
    if looks_like_place(v):
        return "NG", "職種に地名形式(○○区/市/町/村/駅)を含む"

    # (B) 募集・条件・雇用形態・勤務時間・役割 → 要確認
    if any(t in v for t in JOB_CONDITION_TOKENS):
        return "要確認", "職種に募集・雇用形態・勤務時間・役割・条件の混在の可能性"

    # (C) 数字を含む → 要確認 (管理番号など職種と無関係)
    if re.search(r'\d', v):
        return "要確認", "職種に数字を含む(管理番号の可能性)"

    return "OK", ""

# 【チェック9】最低賃金判定 - 都道府県抽出および時給換算
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
    【担当者指定の換算ルール】
    - HOUR: そのまま使用
    - DAY: ÷8時間
    - MONTH: ÷160時間 (8h×20日)
    - YEAR: ÷1920時間 (160h×12ヶ月)
    - WEEK: 未定義 → 要確認
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
# 【メインループ - 各行の審査処理】
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
# 【結果保存 - 3つのシートに分類】
# ============================================================
with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
    df_out.to_excel(writer, sheet_name="審査結果", index=False)  # 全体結果
    df_out[df_out["判定(総合)"] == "NG"].to_excel(writer, sheet_name="NGのみ", index=False)  # NGのみ抽出
    df_out[df_out["判定(総合)"] == "要確認"].to_excel(writer, sheet_name="要確認のみ", index=False)  # 要確認のみ抽出

print("✅ 処理完了:", OUT_XLSX)
print("🔹 最低賃金: 担当者換算(日給8h/月160h/年1920h)、週給は要確認")
print("🔹 都道府県: GFJ → 住所 → 市区町村 → 職種/会社 順序で補完")
print("🔹 職種判定: 地域名・地名形式はNG、募集・条件・数字は要確認")