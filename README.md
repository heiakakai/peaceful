# 교회 재정 프로그램 (Streamlit)

## 실행 방법
1) Python 3.10+ 권장  
2) 설치
```bash
pip install -r requirements.txt
```
3) 실행
```bash
streamlit run app.py
```

## 구성
- 기본정보(로그인): `app.py`
- 재정장부(입력): `pages/1_재정장부_입력.py`
- 재정장부(보고): `pages/2_재정장부_보고.py`
- 일계표/월계표/년계표/예산안: 빈 페이지(추후 구현)

## 데이터 저장
- 자동 저장: 입력 페이지에서 수정 시 즉시 저장됩니다.
- 저장 위치: `data/church_finance.db` (SQLite)

## 엑셀 내보내기
- 상단바 오른쪽에서 **전체 엑셀(.xlsx)** 다운로드 가능
- 입력 페이지에서 **선택한 날짜 장부 다운로드(.xlsx)** 가능


## 상단 메뉴 사용(사이드바 숨김)
- 기본 사이드바 네비게이션은 `.streamlit/config.toml`의 `[client] showSidebarNavigation = false` 설정으로 숨겨져 있습니다.
"# peaceful" 
"# peaceful" 
"# peaceful" 
