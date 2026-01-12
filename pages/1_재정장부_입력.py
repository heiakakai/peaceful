# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from utils.ui import apply_global_style, render_header, render_top_nav, church_date_picker
from utils.auth import require_login
from utils.storage import fetch_day, save_day, INCOME_COLS, EXPENSE_COLS
from utils.exporter import export_day_xlsx

USAGE_OPTIONS = ["은행", "현금"]

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

DEFAULT_ROWS = 200  # 엑셀 복붙 편의

st.set_page_config(page_title="재정장부(입력)", page_icon="📝", layout="wide", initial_sidebar_state="collapsed")
apply_global_style()
render_top_nav("재정장부(입력)")
render_header("재정장부 (입력)", "좌측은 수입, 우측은 지출입니다. 저장은 '지금 저장' 버튼으로 진행합니다.")

if not require_login():
    st.stop()

selected_date = church_date_picker(prefix="in")
income_key = "in_income_work"
expense_key = "in_expense_work"

def _ensure_rows(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """항상 DEFAULT_ROWS 이상이 되도록 행을 확보하고, 날짜/금액 타입을 정리합니다."""
    if df is None or df.empty:
        df = pd.DataFrame(columns=cols)
    # 컬럼 누락 보정
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()

    # 금액을 숫자로 유지
    if "금액" in df.columns:
        df["금액"] = pd.to_numeric(df["금액"], errors="coerce")

    # DEFAULT_ROWS 확보: concat 대신 reindex 사용(불필요한 FutureWarning 회피)
    df = df.reindex(range(max(DEFAULT_ROWS, len(df)))).copy()

    # 날짜는 비어있으면 선택 날짜로 채움
    if "날짜" in df.columns:
        df["날짜"] = df["날짜"].fillna(selected_date)

    return df

# 날짜 변경 시 DB에서 로드
state_date_key = "in_selected_date"
if st.session_state.get(state_date_key) != selected_date.isoformat():
    inc, exp = fetch_day(selected_date)
    st.session_state[income_key] = _ensure_rows(inc, INCOME_COLS)
    st.session_state[expense_key] = _ensure_rows(exp, EXPENSE_COLS)
    st.session_state[state_date_key] = selected_date.isoformat()

# 현재 작업 DF
if income_key not in st.session_state:
    st.session_state[income_key] = _ensure_rows(pd.DataFrame(columns=INCOME_COLS), INCOME_COLS)
if expense_key not in st.session_state:
    st.session_state[expense_key] = _ensure_rows(pd.DataFrame(columns=EXPENSE_COLS), EXPENSE_COLS)

income_df = st.session_state[income_key]
expense_df = st.session_state[expense_key]

income_total = float(pd.to_numeric(income_df["금액"], errors="coerce").fillna(0).sum())
expense_total = float(pd.to_numeric(expense_df["금액"], errors="coerce").fillna(0).sum())

left, right = st.columns(2, gap="large")

def _append_row(which: str):
    key = income_key if which == "income" else expense_key
    cols = INCOME_COLS if which == "income" else EXPENSE_COLS
    df = st.session_state.get(key, pd.DataFrame(columns=cols)).copy()
    df = _ensure_rows(df, cols)
    # 맨 끝에 1행 추가
    row = {c: None for c in cols}
    row["날짜"] = selected_date
    df.loc[len(df)] = row
    st.session_state[key] = df
    st.rerun()

with left:
    st.markdown('<div class="section-title">일별 헌금 수입 명세서</div>', unsafe_allow_html=True)
    st.metric("합계 금액", f"₩{income_total:,.0f}")
    st.button("➕ 수입 행 추가(날짜 자동)", key="add_income_row", on_click=_append_row, args=("income",), width="stretch")

    edited_income = st.data_editor(
        income_df,
        num_rows="fixed",
        width="stretch",
        hide_index=True,
        column_config={
            "날짜": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
            "적요": st.column_config.SelectboxColumn("적요", options=USAGE_OPTIONS),
            "수입항목": st.column_config.SelectboxColumn("수입항목", options=INCOME_ITEMS),
            "수입내역": st.column_config.TextColumn("수입내역"),
            "금액": st.column_config.NumberColumn("금액(원)", min_value=0, step=1, format="accounting"),
            "비고": st.column_config.TextColumn("비고"),
        },
        key=income_key,
    )

with right:
    st.markdown('<div class="section-title">일별 헌금 지출 명세서</div>', unsafe_allow_html=True)
    st.metric("합계 금액", f"₩{expense_total:,.0f}")
    st.button("➕ 지출 행 추가(날짜 자동)", key="add_expense_row", on_click=_append_row, args=("expense",), width="stretch")

    edited_expense = st.data_editor(
        expense_df,
        num_rows="fixed",
        width="stretch",
        hide_index=True,
        column_config={
            "날짜": st.column_config.DateColumn("날짜", format="YYYY-MM-DD"),
            "적요": st.column_config.SelectboxColumn("적요", options=USAGE_OPTIONS),
            "지출항목": st.column_config.SelectboxColumn("지출항목", options=EXPENSE_ITEMS),
            "지출내역": st.column_config.TextColumn("지출내역"),
            "금액": st.column_config.NumberColumn("금액(원)", min_value=0, step=1, format="accounting"),
            "비고": st.column_config.TextColumn("비고"),
        },
        key=expense_key,
    )

st.divider()

# 저장/다운로드
c1, c2 = st.columns([1, 1], gap="small")

def _save_now():
    try:
        save_day(selected_date, st.session_state[income_key], st.session_state[expense_key])
        st.toast("저장 완료", icon="💾")
    except Exception as e:
        st.error("저장 중 오류가 발생했습니다.")
        st.caption(str(e))

c1.button("지금 저장", key="save_now_btn", on_click=_save_now, width="stretch")

try:
    day_xlsx = export_day_xlsx(selected_date, st.session_state[income_key], st.session_state[expense_key])
    c2.download_button(
        "선택한 날짜 장부 다운로드 (.xlsx)",
        data=day_xlsx,
        file_name=f"교회재정_일별장부_{selected_date.isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
        key=f"dl_day_{selected_date.isoformat()}",
    )
except Exception as e:
    st.warning("선택한 날짜의 엑셀 파일을 만들지 못했습니다.")
    st.caption(str(e))
