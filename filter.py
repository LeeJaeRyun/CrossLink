# -*- coding: utf-8 -*-
"""
filter2.py

[목표]
JobMasterList CSV를 읽어:
- ハピリク原稿審査マニュアル NG 조건(메일, 고용형태, 직종 혼입, 회사명 특수기호, 비공개+紹介회사 공란, 市区町村 문자깨짐 등) 1차 체크
- 最低賃金判定: CQ(給与形態 unitText:1~5) + CR(給与下限 minValue)만 사용 (AF: 給与 텍スト는 사용하지 않음)
- 필수항목 체크: 열이 없으면 NG가 아니라 要確認, 값이 비면 NG

[출력]
Downloads 폴더에 Excel(.xlsx) 저장:
- 審査結果 (전체)
- NGのみ
- 要確認のみ
"""

import os
import re
import pandas as pd
from datetime import datetime

# ============================================================
# 0) 경로 설정
# ============================================================
USER_HOME = os.path.expanduser("~")
DOWNLOADS = os.path.join(USER_HOME, "Downloads")

CSV_NAME = "JobMasterList_202601051629.csv"  # CSV 파일명
CSV_PATH = os.path.join(DOWNLOADS, CSV_NAME)

OUT_XLSX_BASE = "審査結果_JobMasterList_202601051629.xlsx"
OUT_XLSX = os.path.join(DOWNLOADS, OUT_XLSX_BASE)

# 파일이 이미 존재하면 타임스탬프 붙여 새로 저장 (권한/덮어쓰기 문제 예방)
if os.path.exists(OUT_XLSX):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_XLSX = os.path.join(DOWNLOADS, f"審査結果_JobMasterList_202601051629_{ts}.xlsx")

# ============================================================
# 1) 最低賃金(令和7年度) - 엔/시간
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

# ============================================================
# 2) マニュアル: 허용 고용형태(完全一致)
# ============================================================
ALLOWED_EMPLOYMENT = {
    "正社員","契約社員","派遣社員","パート","アルバイト",
    "アルバイト・パート","アルバイト/パート","アルバイト／パート","アルバイト、パート",
    "パート・アルバイト","パート/アルバイト","パート／アルバイト","パート、アルバイト",
    "業務委託",
}

# ============================================================
# 3) 정규식/유틸
# ============================================================
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
SPECIAL_COMPANY_MARKS = ["㈱", "（株）", "(株)", "㈲", "（有）", "(有)"]

# 피드백: CQ(給与形態 unitText) 규칙
UNIT_MAP = {
    1: "HOUR",   # 時給
    2: "DAY",    # 日給
    3: "MONTH",  # 月給
    4: "YEAR",   # 年俸
    5: "WEEK",   # 週給
}

def safe_strip(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except:
        pass
    return str(x).strip()

def to_int_safe(x):
    try:
        if x is None or pd.isna(x):
            return None
        return int(float(x))
    except:
        return None

def to_float_safe(x):
    try:
        if x is None or pd.isna(x):
            return None
        return float(x)
    except:
        return None

def pick_col(df, candidates):
    """
    컬럼 매핑:
    - 1) 완전일치 우선
    - 2) 부분일치(너무 짧은 패턴은 제외)
    """
    cols = list(df.columns)
    for c in candidates:
        if c in cols:
            return c
    for c in candidates:
        if len(c) < 3:
            continue
        for col in cols:
            if c in col:
                return col
    return None

def has_garbled_text(s: str) -> bool:
    """문자깨짐/이상문자 1차 탐지"""
    if not isinstance(s, str) or s.strip() == "":
        return False
    if " " in s:
        return True
    if re.search(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", s):
        return True
    if re.search(r"闖|驥|伴", s):
        return True
    return False

# ============================================================
# 4) CSV 로드: 인코딩 자동 감지 (utf-8-sig → cp932 → utf-8)
# ============================================================
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {CSV_PATH}")

df = None
last_err = None
for enc in ["utf-8-sig", "cp932", "utf-8"]:
    try:
        df = pd.read_csv(CSV_PATH, encoding=enc)
        break
    except Exception as e:
        last_err = e

if df is None:
    raise RuntimeError(f"CSV 읽기 실패. 마지막 에러: {last_err}")

# ============================================================
# 5) 컬럼 매핑
# ============================================================
col_work_company  = pick_col(df, ["就業先会社名"])  # U열
col_intro_company = pick_col(df, ["紹介会社名", "紹介元会社名", "紹介元会社", "紹介会社"])  # AO열 계열
col_email         = pick_col(df, ["応募先メールアドレス"])
col_employment    = pick_col(df, ["雇用形態"])
col_job           = pick_col(df, ["職種"])
col_city          = pick_col(df, ["市区町村", "addressLocality"])
col_pref          = pick_col(df, ["都道府県", "addressRegion", "推定都道府県"])

# 최저임금(피드백2): CQ/CR만 사용
col_wage_unit     = pick_col(df, ["給与形態(unitText)", "給与形態（unitText）", "unitText"])  # CQ
col_wage_lower    = pick_col(df, ["給与下限(minValue)", "給与下限（minValue）", "minValue"])  # CR

# AF 給与 텍스트(존재는 참고로만; 최저임금 판정에 사용 X)
# 給与는 자유입력 텍스트라 자동 파싱이 불안정해서 오판 리스크가 크고, unitText/minValue는 구조화된 값이라 재현성과 근거가 명확해서 
# 최저임금 자동 판정은 CQ/CR만 사용합니다. 給与는 참고/불일치 확인 용도로만 유지합니다.
col_salary_text   = pick_col(df, ["給与"])

print("=== 컬럼 매핑(반드시 확인) ===")
print("就業先会社名:", col_work_company)
print("紹介会社名(参照):", col_intro_company)
print("応募先メールアドレス:", col_email)
print("雇用形態:", col_employment)
print("職種:", col_job)
print("市区町村:", col_city)
print("都道府県:", col_pref)
print("給与形態(unitText):", col_wage_unit)
print("給与下限(minValue):", col_wage_lower)
print("給与(自由入力・参考):", col_salary_text)
print("================================")

# ============================================================
# 6) 체크 함수
# ============================================================

# 필수항목: "열 없음" -> 要確認 / "값 공란" -> NG
REQUIRED_FIELDS = [
    ("就業先会社名", col_work_company),
    ("雇用形態", col_employment),
    ("職種", col_job),
    ("応募先メールアドレス", col_email),
    ("都道府県", col_pref),
    ("給与形態(unitText)", col_wage_unit),
    ("給与下限(minValue)", col_wage_lower),
]

def check_required_fields(row):
    """필수항목 누락 여부: 열 없으면 요확인, 값 공란이면 NG"""
    missing_values = []
    missing_columns = []
    for label, col in REQUIRED_FIELDS:
        if not col:
            missing_columns.append(label)
            continue
        v = safe_strip(row.get(col))
        if v == "":
            missing_values.append(label)

    if missing_values:
        return ("NG", "必須項目が空欄: " + ", ".join(missing_values))

    if missing_columns:
        return ("要確認", "必須列が見つからない: " + ", ".join(missing_columns))

    return ("OK", "")

def check_email(row):
    """이메일 형식 유효성"""
    if not col_email:
        return ("要確認", "応募先メール列なし")
    v = safe_strip(row.get(col_email))
    if v == "":
        return ("NG", "応募先メールが空欄")
    parts = [p.strip() for p in v.split(",") if p.strip()]
    if not parts:
        return ("NG", "応募先メールが空欄")
    for p in parts:
        if not EMAIL_RE.match(p):
            return ("NG", "メール形式不正")
    return ("OK", "")

def check_employment(row):
    """고용형태가 허용 목록에 있는지 확인"""
    if not col_employment:
        return ("要確認", "雇用形態列なし")
    v = safe_strip(row.get(col_employment))
    if v == "":
        return ("NG", "雇用形態が空欄")
    if v not in ALLOWED_EMPLOYMENT:
        return ("NG", f"雇用形態が許可表記と不一致: {v}")
    return ("OK", "")

def check_job_title(row):
    """직종명에 조건/광고문구 혼입 여부"""
    if not col_job:
        return ("要確認", "職種列なし")
    v = safe_strip(row.get(col_job))
    if v == "":
        return ("NG", "職種が空欄")
    bad_tokens = [
        "未経験","在宅","リモート","オープニング","募集",
        "上場","部長","勤務地","正社員","契約社員","派遣社員","アルバイト","パート"
    ]
    if any(t in v for t in bad_tokens):
        return ("要確認", "職種に条件/広告文言混在の可能性")
    return ("OK", "")

def check_work_company_name_format(row):
    """就業先会社名에 특수기호(㈱ 등) 포함 여부"""
    if not col_work_company:
        return ("要確認", "就業先会社名列なし")
    v = safe_strip(row.get(col_work_company))
    if v == "":
        return ("NG", "就業先会社名が空欄")
    if any(mark in v for mark in SPECIAL_COMPANY_MARKS):
        return ("NG", "就業先会社名に特殊記号(㈱等)を含む")
    return ("OK", "")

def check_private_intro_company(row):
    """
    - 就業先会社名 == 非公開
    - かつ 紹介会社名(또는 紹介元会社名) == 空欄 → NG
    - 非公開 + 雇用形態が派遣社員 → NG
    """
    if not col_work_company:
        return ("要確認", "就業先会社名列なし")

    work_company = safe_strip(row.get(col_work_company))
    if work_company != "非公開":
        return ("OK", "")

    # 소개회사 열이 아예 없으면 NG시키지 않고 要確認로 남김
    if not col_intro_company:
        return ("要確認", "紹介会社名列が見つからない(非公開案件)")

    intro = safe_strip(row.get(col_intro_company))
    if intro == "":
        return ("NG", "就業先会社名が非公開かつ紹介会社名が空欄")

    if col_employment:
        emp = safe_strip(row.get(col_employment))
        if emp == "派遣社員":
            return ("NG", "就業先会社名が非公開かつ雇用形態が派遣社員")
    return ("OK", "")

def check_city_gfj(row):
    """시구정촌 필드 유효성 & 문자깨짐 탐지"""
    if not col_city:
        return ("要確認", "市区町村列なし")
    v = safe_strip(row.get(col_city))
    if v == "":
        return ("要確認", "市区町村が空欄")
    if has_garbled_text(v):
        return ("NG", "市区町村に文字化けの可能性")
    return ("OK", "")

def judge_min_wage(row):
    """
    - 최저임금 판정은 CQ(unitText) + CR(minValue)만 사용
    - AF(給与) 텍스트는 사용하지 않음
    """
    # 都道府県
    if not col_pref:
        return ("要確認", "都道府県列なし", None, None, None, "列不足")
    pref = safe_strip(row.get(col_pref))
    if pref == "" or pref not in MIN_WAGE:
        return ("要確認", "都道府県不明", pref, None, None, "都道府県不明")

    minw = float(MIN_WAGE[pref])

    if not col_wage_unit:
        return ("要確認", "給与形態(unitText)列なし", pref, minw, None, "列不足")
    if not col_wage_lower:
        return ("要確認", "給与下限(minValue)列なし", pref, minw, None, "列不足")

    unit_code = to_int_safe(row.get(col_wage_unit))
    unit = UNIT_MAP.get(unit_code, "UNKNOWN")
    lower = to_float_safe(row.get(col_wage_lower))

    # 시급(HOUR)만 자동 확정
    if unit == "HOUR":
        if lower is None:
            return ("要確認", "時給だが下限なし", pref, minw, lower, "HOUR下限なし")
        return ("OK", "") if lower >= minw else ("NG", f"最低賃金未満(時給{lower} < {minw})", pref, minw, lower, "HOUR比較")

    # 그 외는 환산 필요 → 要確認
    return ("要確認", f"時給以外({unit})", pref, minw, lower, "換算必要")

# ============================================================
# 7) 실행 및 결과 생성
# ============================================================
out_rows = []

for _, row in df.iterrows():
    req_s, req_r   = check_required_fields(row)
    email_s, email_r = check_email(row)
    emp_s, emp_r   = check_employment(row)
    job_s, job_r   = check_job_title(row)
    comp_s, comp_r = check_work_company_name_format(row)
    priv_s, priv_r = check_private_intro_company(row)
    city_s, city_r = check_city_gfj(row)

    mw_s, mw_r, mw_pref, mw_minw, mw_lower, mw_basis = judge_min_wage(row)

    statuses = [req_s, email_s, emp_s, job_s, comp_s, priv_s, city_s, mw_s]
    if "NG" in statuses:
        total = "NG"
    elif "要確認" in statuses:
        total = "要確認"
    else:
        total = "OK"

    reason = " / ".join([r for r in [req_r, mw_r, email_r, emp_r, job_r, comp_r, priv_r, city_r] if r])

    unit_code = to_int_safe(row.get(col_wage_unit)) if col_wage_unit else None
    unit_label = UNIT_MAP.get(unit_code, "UNKNOWN") if unit_code is not None else ""

    out_rows.append({
        "判定(総合)": total,
        "理由(要約)": reason,

        # 개별 판정(보기 쉽게)
        "必須項目": req_s,
        "応募先メール": email_s,
        "雇用形態": emp_s,
        "職種": job_s,
        "就業先会社名表記": comp_s,
        "非公開→紹介会社名": priv_s,
        "GFJ市区町村": city_s,
        "最低賃金判定": mw_s,

        # 최저임금 "무엇을 기준으로 판정했는지" 명확화
        "最低賃金_都道府県": mw_pref if mw_pref is not None else safe_strip(row.get(col_pref)) if col_pref else "",
        "最低賃金_基準値(円/時)": mw_minw if mw_minw is not None else (MIN_WAGE.get(safe_strip(row.get(col_pref))) if col_pref else ""),
        "給与形態(unitText)": unit_code if unit_code is not None else (safe_strip(row.get(col_wage_unit)) if col_wage_unit else ""),
        "給与形態(解釈)": unit_label,
        "給与下限(minValue)": mw_lower if mw_lower is not None else (row.get(col_wage_lower) if col_wage_lower else ""),
        "最低賃金_判定根拠": mw_basis,

        # 소개회사 매핑 디버그(OK가 NG로 잘못 떨어질 때 원인 추적용)
        "紹介会社名_参照列": col_intro_company if col_intro_company else "",
        "紹介会社名_値": safe_strip(row.get(col_intro_company)) if col_intro_company else "",
    })

