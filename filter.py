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