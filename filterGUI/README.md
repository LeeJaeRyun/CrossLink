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