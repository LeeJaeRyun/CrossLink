## filterGUI

### 이 툴을 사용할 사용자들이 비개발자일 경우인 점을 고려하여 사용하기 쉽게 만들어달라는 요청을 하심에 따라 추가함
### GUI + exe로 배포

### 시나리오
사용자: FilteredTool.exe 더블클릭 → 창 뜸 → CSV 선택 → 실행
결과: Downloads\Filtered_list_YYYYMMDD_HHMMSS.xlsx 생성
완료 메시지 + “폴더 열기” 버튼

### 사용 방법 (exe 생성 절차)
1. 필요한 라이브러리 설치 (최초 1회)
   pip install pandas openpyxl pyinstaller

2. filter_core.py 와 gui_app.py 가 있는 디렉터리에서 아래 명령어 실행
   pyinstaller --onefile --noconsole --name FilteredTool gui_app.py

### [GUI ↔ Core 연결 구조]
```
gui_app.py  (GUI 진입점)
    │
    ├─ CSV 파일 선택 UI
    │
    ├─ [실행] 버튼 클릭
    │
    └─ run() 메서드 호출
        │
        ▼
filter_core.run_filter(csv_path, out_xlsx)
        │
        ├─ CSV 인코딩 자동 감지
        │     ├─ utf-8-sig
        │     ├─ cp932
        │     └─ utf-8
        │
        ├─ 심사 체크 로직 실행 (총 9개)
        │     ├─ check_required()              # 필수 항목 누락 여부
        │     ├─ check_email()                 # 이메일 형식 검증
        │     ├─ check_employment()            # 고용 형태 검증
        │     ├─ check_company_special()       # 회사명 특수문자
        │     ├─ check_intro_company_special() # 소개회사 특수문자
        │     ├─ check_private_intro()         # 비공개 + 소개회사 공란
        │     ├─ check_city_garbled()           # 시/구/동 문자 깨짐
        │     ├─ check_job_title()              # 직종 혼입 여부
        │     └─ judge_min_wage()               # 최저임금 판정
        │
        ├─ 심사 결과 DataFrame 생성
        │
        └─ Excel(.xlsx) 저장 (3개 시트)
              ├─ 審査結果     : 전체 결과
              ├─ NGのみ       : NG 항목만
              └─ 要確認のみ   : 요확인 항목만
        │
        ▼
   결과 파일 경로 반환
        │
        ▼
gui_app.py
    ├─ GUI 상태 업데이트 (완료 메시지 등)
    └─ 결과 폴더 자동 오픈
```