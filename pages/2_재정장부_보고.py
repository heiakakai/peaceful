# -*- coding: utf-8 -*-
import calendar
import datetime as dt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from utils.ui import apply_global_style, render_header, render_top_nav, church_date_picker
from utils.auth import require_login
from utils.storage import fetch_day, fetch_range
from utils.exporter import export_tables_xlsx

INCOME_ITEMS = [
    "십일조", "주정헌금", "감사헌금", "선교헌금", "건축헌금", "차량헌금", "구제헌금",
    "신년감사헌금", "부활절감사헌금", "맥추감사헌금", "추수감사헌금", "성탄감사헌금",
    "작정헌금", "기타", "대출금", "예치금", "이월금"
]
EXPENSE_ITEMS = [
    "재정부", "예배부", "선교부", "차량부", "관리부", "식당봉사부", "새신자전도부",
    "주일학교", "중고청년", "사례비1", "사례비2", "전기요금", "가스요금", "전화요금등", "상하수도요금",
    "사택관리", "대출금이자", "화재보험료", "대출원금 상환", "예치금", "이월금"
]
EXCLUDE_FOR_NET = {"예치금", "이월금"}

st.set_page_config(page_title="재정장부(보고)", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
apply_global_style()
render_top_nav("재정장부(보고)")
render_header("재정장부 (보고)", "보고 단위를 선택해 기간별 항목 합계/비율을 확인합니다.")

if not require_login():
    st.stop()

# 보고 모드: 체크박스(단일 선택처럼 동작하도록 강제)
modes = ["일 보고", "주 보고", "월 보고", "분기 보고", "년 보고"]
if "report_mode" not in st.session_state:
    st.session_state["report_mode"] = "일 보고"

# 매 실행마다 현재 모드 1개만 True로 동기화(중복 체크 방지)
cur_mode = st.session_state.get("report_mode", "일 보고")
for m in modes:
    st.session_state[f"cb_{m}"] = (m == cur_mode)

def _on_mode_toggle(m: str):
    # 사용자가 m을 체크하면, 나머지는 해제
    if st.session_state.get(f"cb_{m}"):
        st.session_state["report_mode"] = m
        for other in modes:
            if other != m:
                st.session_state[f"cb_{other}"] = False
    else:
        # 활성 모드를 끄려고 하면 다시 켜서 '항상 1개 선택' 유지
        if st.session_state.get("report_mode") == m:
            st.session_state[f"cb_{m}"] = True

c = st.columns([1, 1, 1, 1, 1], gap="small")
for i, m in enumerate(modes):
    c[i].checkbox(m, key=f"cb_{m}", on_change=_on_mode_toggle, args=(m,))

mode = st.session_state.get("report_mode", "일 보고")

# 기본 날짜 선택
base_date = church_date_picker(prefix="rp")

def sundays_of_month(y: int, m: int):
    cal = calendar.monthcalendar(y, m)
    out = []
    for w in cal:
        d = w[calendar.SUNDAY]
        if d != 0:
            out.append(dt.date(y, m, d))
    return out

def closest_past_sunday(d: dt.date) -> dt.date:
    sundays = sundays_of_month(d.year, d.month)
    past = [s for s in sundays if s <= d]
    return past[-1] if past else sundays[0]

def date_range_for_mode(d: dt.date, mode: str):
    if mode == "일 보고":
        return d, d, f"{d.year}년 {d.month}월 {d.day}일"
    if mode == "주 보고":
        sun = closest_past_sunday(d)
        start = sun
        end = sun + dt.timedelta(days=6)
        last_day = calendar.monthrange(d.year, d.month)[1]
        month_end = dt.date(d.year, d.month, last_day)
        if end > month_end:
            end = month_end
        week_idx = sundays_of_month(d.year, d.month).index(sun) + 1
        return start, end, f"{d.year}년 {d.month}월 {week_idx}주차"
    if mode == "월 보고":
        start = dt.date(d.year, d.month, 1)
        end = dt.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
        return start, end, f"{d.year}년 {d.month}월"
    if mode == "분기 보고":
        q = (d.month - 1) // 3 + 1
        sm = (q - 1) * 3 + 1
        em = sm + 2
        start = dt.date(d.year, sm, 1)
        end = dt.date(d.year, em, calendar.monthrange(d.year, em)[1])
        return start, end, f"{d.year}년 {q}/4분기"
    if mode == "년 보고":
        start = dt.date(d.year, 1, 1)
        end = dt.date(d.year, 12, 31)
        return start, end, f"{d.year}년"
    return d, d, f"{d.year}-{d.month}-{d.day}"

start, end, title_suffix = date_range_for_mode(base_date, mode)
title = f"{title_suffix} 평안한교회 재정보고"
st.markdown(f"## {title}")
st.caption(f"기간: {start.isoformat()} ~ {end.isoformat()}")

# 데이터 로드
if start == end:
    income_df, expense_df = fetch_day(start)
else:
    income_df, expense_df = fetch_range(start, end)

if income_df is None or income_df.empty:
    income_df = pd.DataFrame(columns=["수입항목", "금액"])
if expense_df is None or expense_df.empty:
    expense_df = pd.DataFrame(columns=["지출항목", "금액"])

income_df["금액"] = pd.to_numeric(income_df.get("금액"), errors="coerce").fillna(0)
expense_df["금액"] = pd.to_numeric(expense_df.get("금액"), errors="coerce").fillna(0)

income_total = float(income_df["금액"].sum())
expense_total = float(expense_df["금액"].sum())

def usage_stats(df: pd.DataFrame, total: float) -> dict:
    """적요(현금/은행) 기준 합계/비율"""
    if df is None or df.empty or "적요" not in df.columns:
        cash = 0.0
        bank = 0.0
    else:
        cash = float(df.loc[df["적요"] == "현금", "금액"].sum())
        bank = float(df.loc[df["적요"] == "은행", "금액"].sum())
    denom = total if total > 0 else 0.0
    cash_ratio = (cash / denom * 100.0) if denom > 0 else 0.0
    bank_ratio = (bank / denom * 100.0) if denom > 0 else 0.0
    return {"cash": cash, "bank": bank, "cash_ratio": cash_ratio, "bank_ratio": bank_ratio}

income_usage = usage_stats(income_df, income_total)
expense_usage = usage_stats(expense_df, expense_total)
net_balance = income_total - expense_total


def make_summary(df: pd.DataFrame, item_col: str, full_items: list[str]) -> pd.DataFrame:
    base = pd.DataFrame({item_col: full_items})
    if df.empty or item_col not in df.columns:
        s = base.copy()
        s["합계"] = 0
    else:
        s = (
            df.groupby(item_col, dropna=False)["금액"].sum()
              .reset_index()
              .rename(columns={"금액": "합계"})
        )
        s[item_col] = s[item_col].fillna("(미지정)")
        s = base.merge(s, on=item_col, how="left")
        s["합계"] = s["합계"].fillna(0)

    denom = float(s["합계"].sum())
    if denom <= 0:
        s["비율(%)"] = 0.0
    else:
        s["비율(%)"] = s.apply(lambda r: (float(r["합계"]) / denom * 100.0), axis=1)

    s["합계"] = s["합계"].round(0).astype(int)
    s["비율(%)"] = s["비율(%)"].round(1)
    return s

income_sum = make_summary(income_df, "수입항목", INCOME_ITEMS)
expense_sum = make_summary(expense_df, "지출항목", EXPENSE_ITEMS)

# 표 최하단에 합계/순합계 행 추가(사용자 요청)
def with_totals(summary: pd.DataFrame, item_col: str, total_amount: float) -> pd.DataFrame:
    summary = summary.copy()
    try:
        net_sum = int(summary[~summary[item_col].isin(EXCLUDE_FOR_NET)]["합계"].sum())
    except Exception:
        net_sum = 0
    total_row = {item_col: "합계 금액", "합계": int(round(total_amount, 0)), "비율(%)": float("nan")}
    net_row = {item_col: "순합계(예치금/이월금 제외)", "합계": int(round(net_sum, 0)), "비율(%)": float("nan")}
    return pd.concat([summary, pd.DataFrame([total_row, net_row])], ignore_index=True)

income_sum = with_totals(income_sum, "수입항목", income_total)
expense_sum = with_totals(expense_sum, "지출항목", expense_total)

# 상단 요약(총수입/총지출/순잔액)
sum_cols = st.columns(3, gap="small")
sum_cols[0].metric("총수입", f"₩{income_total:,.0f}")
sum_cols[1].metric("총지출", f"₩{expense_total:,.0f}")
sum_cols[2].metric("순잔액(총수입-총지출)", f"₩")

st.divider()

left, right = st.columns(2, gap="large")
with left:
    st.markdown("### 수입")
    st.metric("총 합계금액", f"₩{income_total:,.0f}")

    usage_df = pd.DataFrame([
        {"구분": "현금", "합계": f"₩{income_usage['cash']:,.0f}", "비율": f"{income_usage['cash_ratio']:.1f}%"},
        {"구분": "은행", "합계": f"₩{income_usage['bank']:,.0f}", "비율": f"{income_usage['bank_ratio']:.1f}%"},
    ])
    st.dataframe(income_sum.style.format({"합계": "{:,.0f}", "비율(%)": lambda v: "" if pd.isna(v) else f"{float(v):.1f}%" }), width="stretch", hide_index=True)

with right:
    st.markdown("### 지출")
    st.metric("총 합계금액", f"₩{expense_total:,.0f}")

    usage_df = pd.DataFrame([
        {"구분": "현금", "합계": f"₩{expense_usage['cash']:,.0f}", "비율": f"{expense_usage['cash_ratio']:.1f}%"},
        {"구분": "은행", "합계": f"₩{expense_usage['bank']:,.0f}", "비율": f"{expense_usage['bank_ratio']:.1f}%"},
    ])
    st.dataframe(expense_sum.style.format({"합계": "{:,.0f}", "비율(%)": lambda v: "" if pd.isna(v) else f"{float(v):.1f}%" }), width="stretch", hide_index=True)


st.divider()
st.markdown("### 적요(현금/은행)별 합계/비율")
u1, u2 = st.columns(2, gap="large")

def _usage_df(kind: str, usage: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {"구분": "현금", "합계": int(round(usage["cash"], 0)), "비율(%)": round(float(usage["cash_ratio"]), 1)},
        {"구분": "은행", "합계": int(round(usage["bank"], 0)), "비율(%)": round(float(usage["bank_ratio"]), 1)},
    ])

income_usage_df = _usage_df("수입", income_usage)
expense_usage_df = _usage_df("지출", expense_usage)

def _fmt_usage(df: pd.DataFrame) -> pd.DataFrame:
    disp = df.copy()
    disp["합계"] = disp["합계"].apply(lambda v: f"₩{int(v):,}")
    disp["비율(%)"] = disp["비율(%)"].apply(lambda v: f"{float(v):.1f}%")
    return disp

with u1:
    st.markdown("#### 수입")
    st.dataframe(_fmt_usage(income_usage_df), width="stretch", hide_index=True)
with u2:
    st.markdown("#### 지출")
    st.dataframe(_fmt_usage(expense_usage_df), width="stretch", hide_index=True)
# 엑셀 다운로드
try:
    xlsx = export_tables_xlsx(
        filename_prefix=f"재정보고_{title_suffix}",
        sheets={"수입": income_sum, "지출": expense_sum},
        money_columns=["합계"],
    )
    st.download_button(
        "이 보고서 다운로드 (.xlsx)",
        data=xlsx,
        file_name=f"재정보고_{title_suffix}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
        key=f"dl_report_{title_suffix}",
    )
except Exception as e:
    st.caption("엑셀 다운로드 준비 실패")
    st.caption(str(e))

st.divider()

print_date_line = f"{base_date.year}년 {base_date.month}월 {base_date.day}일"

with st.expander("🖨️ 인쇄용 보기 (Ctrl+P / ⌘+P)"):
    def df_to_html(df: pd.DataFrame, kind: str, total: float) -> str:
        rows = []
        for _, r in df.iterrows():
            ratio = r.get("비율(%)")
            ratio_txt = "" if pd.isna(ratio) else f"{float(ratio):.1f}%"
            rows.append(
                f"<tr><td>{r.iloc[0]}</td><td style='text-align:right'>₩{int(r['합계']):,}</td><td style='text-align:right'>{ratio_txt}</td></tr>"
            )
        body = "\n".join(rows)
        return f"""
        <div class='box'>
          <h3>{kind}</h3>
          <div class='total'>총 합계금액: <b>₩{total:,.0f}</b></div>
          <table>
            <thead><tr><th>항목</th><th>합계</th><th>비율</th></tr></thead>
            <tbody>{body}</tbody>
          </table>
        </div>
        """

    def usage_to_html(kind: str, usage: dict) -> str:
        return f"""
        <table class='mini'>
          <thead><tr><th colspan='3'>{kind} 적요별</th></tr></thead>
          <tbody>
            <tr><td>현금</td><td style='text-align:right'>₩{usage['cash']:,.0f}</td><td style='text-align:right'>{usage['cash_ratio']:.1f}%</td></tr>
            <tr><td>은행</td><td style='text-align:right'>₩{usage['bank']:,.0f}</td><td style='text-align:right'>{usage['bank_ratio']:.1f}%</td></tr>
          </tbody>
        </table>
        """

    approval = """
    <table class='approval'>
      <tr>
        <th>담당</th><th>부장</th><th>목사</th>
      </tr>
      <tr>
        <td class='sign'>&nbsp;</td><td class='sign'>&nbsp;</td><td class='sign'>&nbsp;</td>
      </tr>
    </table>
    """

    html = f"""
    <html>
    <head>
      <meta charset="utf-8"/>
      <style>
        body {{ font-family: Arial, sans-serif; padding: 10px; }}
        .titlebar {{ display:flex; justify-content: space-between; align-items:flex-start; gap: 12px; }}
        .titletext {{ font-size: 32px; font-weight: 800; line-height: 1.2; }}
        .period {{ margin: 6px 0 10px 0; font-size: 12px; color:#666; }}

        .approval {{ border-collapse: collapse; font-size: 9px; width: 150px; margin-left:auto; }}
        .approval th, .approval td {{ border: 1px solid #333; padding: 3px; text-align:center; width: 50px; }}
        .approval .sign {{ height: 45px; }}

        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
        .box {{ border: 1px solid #ddd; border-radius: 10px; padding: 12px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 13px; }}
        th {{ background: #f5f5f5; }}
        .total {{ margin: 8px 0 10px 0; }}

        table.mini th, table.mini td {{ font-size: 12px; padding: 6px; }}
        table.mini thead th {{ background: #f5f5f5; }}

        @media print {{
          body {{ padding: 0; }}
          .box {{ break-inside: avoid; }}
        }}
      </style>
    </head>
    <body>
      <div class="titlebar">
        <div class="titletext">{title_suffix}<br/>평안한교회 재정보고</div>
        {approval}
      </div>

      <div class='grid'>
        {df_to_html(income_sum, "수입", income_total)}
        {df_to_html(expense_sum, "지출", expense_total)}
      </div>
    </body>
    </html>
    """
    components.html(html, height=660, scrolling=True)
