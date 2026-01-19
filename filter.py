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