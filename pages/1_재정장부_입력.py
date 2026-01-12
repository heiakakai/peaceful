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

st.set_page_config(page_title="재정장부(입력)", page_icon="📝", layout="wide", initial_sidebar_state="collapsed")
apply_global_style()
render_top_nav("재정장부(입력)")
render_header("재정장부 (입력)", "좌측은 수입, 우측은 지출입니다. 저장은 '지금 저장' 버튼으로 진행합니다.")

if not require_login():
    st.stop()

selected_date = church_date_picker(prefix="in")
income_key = "in_income_work"
expense_key = "in_expense_work"
def _normalize_df(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """컬럼/타입을 정리하고 필요한 값만 유지합니다."""
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

    # 날짜는 비어있으면 선택 날짜로 채움
    if "날짜" in df.columns:
        df["날짜"] = df["날짜"].fillna(selected_date)

    return df

# 날짜 변경 시 DB에서 로드
state_date_key = "in_selected_date"
if st.session_state.get(state_date_key) != selected_date.isoformat():
    inc, exp = fetch_day(selected_date)
    st.session_state[income_key] = _normalize_df(inc, INCOME_COLS)
    st.session_state[expense_key] = _normalize_df(exp, EXPENSE_COLS)
    st.session_state[state_date_key] = selected_date.isoformat()

# 현재 작업 DF
if income_key not in st.session_state:
    st.session_state[income_key] = _normalize_df(pd.DataFrame(columns=INCOME_COLS), INCOME_COLS)
if expense_key not in st.session_state:
    st.session_state[expense_key] = _normalize_df(pd.DataFrame(columns=EXPENSE_COLS), EXPENSE_COLS)

income_df = st.session_state[income_key]
expense_df = st.session_state[expense_key]

income_total = float(pd.to_numeric(income_df["금액"], errors="coerce").fillna(0).sum())
expense_total = float(pd.to_numeric(expense_df["금액"], errors="coerce").fillna(0).sum())

left, right = st.columns(2, gap="large")

def _add_row(which: str, row: dict) -> None:
    key = income_key if which == "income" else expense_key
    cols = INCOME_COLS if which == "income" else EXPENSE_COLS
    df = st.session_state.get(key, pd.DataFrame(columns=cols)).copy()
    df = _normalize_df(df, cols)
    df.loc[len(df)] = row
    st.session_state[key] = _normalize_df(df, cols)

def _delete_row(which: str, idx: int) -> None:
    key = income_key if which == "income" else expense_key
    cols = INCOME_COLS if which == "income" else EXPENSE_COLS
    df = st.session_state.get(key, pd.DataFrame(columns=cols)).copy()
    if df.empty or idx not in df.index:
        return
    df = df.drop(index=idx).reset_index(drop=True)
    st.session_state[key] = _normalize_df(df, cols)

with left:
    st.markdown('<div class="section-title">일별 헌금 수입 명세서</div>', unsafe_allow_html=True)
    st.metric("합계 금액", f"₩{income_total:,.0f}")
    with st.form("income_form", clear_on_submit=True):
        c1, c2 = st.columns(2, gap="small")
        in_date = c1.date_input("날짜", value=selected_date)
        in_usage = c2.selectbox("적요", USAGE_OPTIONS)
        in_item = st.selectbox("수입항목", INCOME_ITEMS)
        in_detail = st.text_input("수입내역")
        in_amount = st.number_input("금액(원)", min_value=0, step=1, value=0)
        in_note = st.text_input("비고")
        income_submit = st.form_submit_button("수입 추가")
    if income_submit:
        _add_row(
            "income",
            {
                "날짜": in_date,
                "적요": in_usage,
                "수입항목": in_item,
                "수입내역": in_detail,
                "금액": in_amount,
                "비고": in_note,
            },
        )
        st.toast("수입 항목을 추가했습니다.", icon="✅")
        st.rerun()
    st.dataframe(income_df, width="stretch", hide_index=True)
    if not income_df.empty:
        del_idx = st.selectbox(
            "삭제할 수입 행",
            options=list(income_df.index),
            format_func=lambda i: f"{i + 1}행",
            key="income_delete_idx",
        )
        if st.button("선택 수입 행 삭제", key="income_delete_btn", width="stretch"):
            _delete_row("income", del_idx)
            st.toast("수입 행을 삭제했습니다.", icon="🧹")
            st.rerun()

with right:
    st.markdown('<div class="section-title">일별 헌금 지출 명세서</div>', unsafe_allow_html=True)
    st.metric("합계 금액", f"₩{expense_total:,.0f}")
    with st.form("expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2, gap="small")
        ex_date = c1.date_input("날짜", value=selected_date, key="ex_date")
        ex_usage = c2.selectbox("적요", USAGE_OPTIONS, key="ex_usage")
        ex_item = st.selectbox("지출항목", EXPENSE_ITEMS, key="ex_item")
        ex_detail = st.text_input("지출내역", key="ex_detail")
        ex_amount = st.number_input("금액(원)", min_value=0, step=1, value=0, key="ex_amount")
        ex_note = st.text_input("비고", key="ex_note")
        expense_submit = st.form_submit_button("지출 추가")
    if expense_submit:
        _add_row(
            "expense",
            {
                "날짜": ex_date,
                "적요": ex_usage,
                "지출항목": ex_item,
                "지출내역": ex_detail,
                "금액": ex_amount,
                "비고": ex_note,
            },
        )
        st.toast("지출 항목을 추가했습니다.", icon="✅")
        st.rerun()
    st.dataframe(expense_df, width="stretch", hide_index=True)
    if not expense_df.empty:
        del_idx = st.selectbox(
            "삭제할 지출 행",
            options=list(expense_df.index),
            format_func=lambda i: f"{i + 1}행",
            key="expense_delete_idx",
        )
        if st.button("선택 지출 행 삭제", key="expense_delete_btn", width="stretch"):
            _delete_row("expense", del_idx)
            st.toast("지출 행을 삭제했습니다.", icon="🧹")
            st.rerun()

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
