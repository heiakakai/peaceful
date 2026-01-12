# -*- coding: utf-8 -*-
import datetime as dt
import pandas as pd
import streamlit as st

from utils.ui import apply_global_style, render_header, render_top_nav
from utils.auth import require_login
from utils.storage import fetch_range
from utils.exporter import export_tables_xlsx

ITEMS = ['재정부', '예배부', '선교부', '차량부', '관리부', '식당봉사부', '새신자전도부', '주일학교', '중고청년', '사례비1', '사례비2', '전기요금', '가스요금', '전화요금등', '상하수도요금', '사택관리', '대출금이자', '화재보험료', '대출원금 상환', '예치금', '이월금']
ITEM_COL = "지출항목"
PAGE_TITLE = "월별 현황(지출)"
ACTIVE_NAV = "월별 현황(지출)"
EXCLUDE = {'이월금', '예치금'}
NET_LABEL = "순지출액"

st.set_page_config(page_title=PAGE_TITLE, page_icon="📆", layout="wide", initial_sidebar_state="collapsed")
apply_global_style()
render_top_nav(ACTIVE_NAV)
render_header(PAGE_TITLE, "선택한 연도의 월별 항목 합계를 확인합니다. (항목은 입력이 없어도 모두 표시)")

if not require_login():
    st.stop()

today = dt.date.today()
years = list(range(today.year - 5, today.year + 6))
year = st.selectbox("년도", years, index=years.index(today.year), key=f"{ACTIVE_NAV}_year")

start = dt.date(year, 1, 1)
end = dt.date(year, 12, 31)

income_df, expense_df = fetch_range(start, end)

df = income_df if ITEM_COL == "수입항목" else expense_df
if df is None or df.empty:
    df = pd.DataFrame(columns=["날짜", ITEM_COL, "금액"])

df["금액"] = pd.to_numeric(df.get("금액"), errors="coerce").fillna(0)
if "날짜" in df.columns and not df.empty:
    df["월"] = pd.to_datetime(df["날짜"]).dt.month
else:
    df["월"] = None

pivot = (
    df.groupby([ITEM_COL, "월"])["금액"].sum().reset_index()
    if not df.empty and "월" in df.columns
    else pd.DataFrame(columns=[ITEM_COL, "월", "금액"])
)

rows = []
for item in ITEMS:
    row = {"구분": item}
    total = 0.0
    for m in range(1, 13):
        if pivot.empty:
            val = 0.0
        else:
            val = float(pivot[(pivot[ITEM_COL] == item) & (pivot["월"] == m)]["금액"].sum())
        row[f"{m}월"] = int(round(val, 0))
        total += val
    row["합계"] = int(round(total, 0))
    rows.append(row)

out = pd.DataFrame(rows)

total_all = float(out["합계"].sum())
excluded_sum = float(out[out["구분"].isin(EXCLUDE)]["합계"].sum())
net_total = total_all - excluded_sum

def ratio(item: str, item_sum: float) -> float:
    if item in EXCLUDE:
        return 0.0
    if net_total <= 0:
        return 0.0
    return (item_sum / net_total) * 100.0

out["비율(%)"] = out.apply(lambda r: round(ratio(r["구분"], float(r["합계"])), 1), axis=1)

# 하단 요약(월별 합계/순합계)
sum_row = {"구분": "합계 금액"}
net_row = {"구분": NET_LABEL}

for m in range(1, 13):
    col = f"{m}월"
    month_total = float(out[col].sum())
    month_excl = float(out[out["구분"].isin(EXCLUDE)][col].sum())
    sum_row[col] = int(round(month_total, 0))
    net_row[col] = int(round(month_total - month_excl, 0))

sum_row["합계"] = int(round(total_all, 0))
sum_row["비율(%)"] = 100.0 if net_total > 0 else 0.0
net_row["합계"] = int(round(net_total, 0))
net_row["비율(%)"] = 100.0 if net_total > 0 else 0.0

out2 = pd.concat([out, pd.DataFrame([sum_row, net_row])], ignore_index=True)

money_cols = [c for c in out2.columns if c.endswith('월') or c == '합계']
ratio_col = '비율(%)'

# 화면 표시용(문자열로 포맷) - Streamlit 버전에 따라 Styler가 적용되지 않는 경우가 있어 안전하게 변환
_disp = out2.copy()
for c in money_cols:
    _disp[c] = _disp[c].apply(lambda v: '' if pd.isna(v) else f"{int(v):,}")
_disp[ratio_col] = _disp[ratio_col].apply(lambda v: '' if pd.isna(v) else f"{float(v):.1f}%")

st.dataframe(_disp, width='stretch', hide_index=True)

st.divider()
with st.expander("🖨️ 인쇄용 보기 (Ctrl+P / ⌘+P)"):
    # 인쇄용 HTML
    title = f"{PAGE_TITLE} - {year}년"
    # 표시용(콤마)
    disp = out2.copy()
    for c in [c for c in disp.columns if c.endswith("월") or c == "합계"]:
        disp[c] = disp[c].apply(lambda x: "" if pd.isna(x) else f"{int(x):,}")
    disp["비율(%)"] = disp["비율(%)"].apply(lambda v: "" if pd.isna(v) else f"{float(v):.1f}%")

    # HTML 테이블 생성
    th = "".join([f"<th>{c}</th>" for c in disp.columns])
    rows = []
    for _, r in disp.iterrows():
        tds = "".join([f"<td style='text-align:right'>&nbsp;{r[c]}</td>" if (c.endswith("월") or c in ["합계","비율(%)"]) else f"<td>{r[c]}</td>" for c in disp.columns])
        rows.append(f"<tr>{tds}</tr>")
    body = "\n".join(rows)

    html = f"""
    <html><head><meta charset='utf-8'/>
    <style>
      body {{ font-family: Arial, sans-serif; padding: 10px; }}
      h2 {{ margin: 0 0 8px 0; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ border: 1px solid #ddd; padding: 6px; font-size: 12px; }}
      th {{ background: #f5f5f5; }}
      @media print {{ body {{ padding:0; }} }}
    </style>
    </head>
    <body>
      <h2>{title}</h2>
      <table>
        <thead><tr>{th}</tr></thead>
        <tbody>{body}</tbody>
      </table>
    </body></html>
    """
    import streamlit.components.v1 as components
    components.html(html, height=560, scrolling=True)


# 엑셀 다운로드
try:
    xlsx = export_tables_xlsx(
        filename_prefix=f"{PAGE_TITLE}_{year}",
        sheets={PAGE_TITLE: out2},
        money_columns=[c for c in out2.columns if c.endswith("월") or c == "합계"],
    )
    st.download_button(
        "이 표 다운로드 (.xlsx)",
        data=xlsx,
        file_name=f"{PAGE_TITLE}_{year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
        key=f"{ACTIVE_NAV}_dl_{year}",
    )
except Exception as e:
    st.warning("엑셀 파일을 만들지 못했습니다.")
    st.caption(str(e))
