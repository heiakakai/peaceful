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

def _coerce_date(value, fallback):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fallback
    if isinstance(value, pd.Timestamp):
        return value.date()
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return fallback

def _coerce_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)

def _coerce_amount(value) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    try:
        return int(float(value))
    except Exception:
        return 0

def _reset_income_form() -> None:
    st.session_state["income_form_date"] = selected_date
    st.session_state["income_form_usage"] = USAGE_OPTIONS[0]
    st.session_state["income_form_item"] = INCOME_ITEMS[0]
    st.session_state["income_form_detail"] = ""
    st.session_state["income_form_amount"] = 0
    st.session_state["income_form_note"] = ""

def _reset_expense_form() -> None:
    st.session_state["expense_form_date"] = selected_date
    st.session_state["expense_form_usage"] = USAGE_OPTIONS[0]
    st.session_state["expense_form_item"] = EXPENSE_ITEMS[0]
    st.session_state["expense_form_detail"] = ""
    st.session_state["expense_form_amount"] = 0
    st.session_state["expense_form_note"] = ""

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

def _upsert_row(which: str, idx: int | None, row: dict) -> None:
    key = income_key if which == "income" else expense_key
    cols = INCOME_COLS if which == "income" else EXPENSE_COLS
    df = st.session_state.get(key, pd.DataFrame(columns=cols)).copy()
    df = _normalize_df(df, cols)
    if idx is not None and idx in df.index:
        df.loc[idx] = row
    else:
        df.loc[len(df)] = row
    st.session_state[key] = _normalize_df(df, cols)

with left:
    st.markdown('<div class="section-title">일별 헌금 수입 명세서</div>', unsafe_allow_html=True)
    st.metric("합계 금액", f"₩{income_total:,.0f}")
    def _income_label(i: int) -> str:
        if i == -1:
            return "신규 입력"
        row = income_df.loc[i]
        d = row.get("날짜")
        date_txt = d.isoformat() if hasattr(d, "isoformat") else str(d)
        usage = row.get("적요") or ""
        item = row.get("수입항목") or ""
        detail = row.get("수입내역") or ""
        amount = row.get("금액")
        amt_txt = f"{int(amount):,}" if pd.notna(amount) else ""
        note = row.get("비고") or ""
        return f"{date_txt} / {usage} / {item} / {detail} / {amt_txt} / {note}"
    income_edit_idx = st.selectbox(
        "수정할 수입 행",
        options=[-1] + list(income_df.index),
        format_func=_income_label,
        key="income_edit_idx",
    )
    if "income_form_date" not in st.session_state:
        _reset_income_form()
    if st.session_state.get("income_edit_last") != income_edit_idx:
        st.session_state["income_edit_last"] = income_edit_idx
        if income_edit_idx in income_df.index:
            income_row = income_df.loc[income_edit_idx]
            st.session_state["income_form_date"] = _coerce_date(income_row.get("날짜"), selected_date)
            usage = income_row.get("적요")
            if usage not in USAGE_OPTIONS:
                usage = USAGE_OPTIONS[0]
            st.session_state["income_form_usage"] = usage
            item = income_row.get("수입항목")
            if item not in INCOME_ITEMS:
                item = INCOME_ITEMS[0]
            st.session_state["income_form_item"] = item
            st.session_state["income_form_detail"] = _coerce_text(income_row.get("수입내역"))
            st.session_state["income_form_amount"] = _coerce_amount(income_row.get("금액"))
            st.session_state["income_form_note"] = _coerce_text(income_row.get("비고"))
        else:
            _reset_income_form()
    with st.form("income_form", clear_on_submit=False):
        c1, c2 = st.columns(2, gap="small")
        in_date = c1.date_input("날짜", key="income_form_date")
        in_usage = c2.selectbox("적요", USAGE_OPTIONS, key="income_form_usage")
        in_item = st.selectbox("수입항목", INCOME_ITEMS, key="income_form_item")
        in_detail = st.text_input("수입내역", key="income_form_detail")
        in_amount = st.number_input("금액(원)", min_value=0, step=1, key="income_form_amount")
        in_note = st.text_input("비고", key="income_form_note")
        income_submit = st.form_submit_button("수입 저장")
    if income_submit:
        _upsert_row(
            "income",
            None if income_edit_idx == -1 else income_edit_idx,
            {
                "날짜": in_date,
                "적요": in_usage,
                "수입항목": in_item,
                "수입내역": in_detail,
                "금액": in_amount,
                "비고": in_note,
            },
        )
        st.session_state["income_edit_idx"] = -1
        st.session_state["income_edit_last"] = -1
        _reset_income_form()
        st.toast("수입 항목을 저장했습니다.", icon="✅")
        st.rerun()
    st.dataframe(income_df, width="stretch", hide_index=True)

with right:
    st.markdown('<div class="section-title">일별 헌금 지출 명세서</div>', unsafe_allow_html=True)
    st.metric("합계 금액", f"₩{expense_total:,.0f}")
    def _expense_label(i: int) -> str:
        if i == -1:
            return "신규 입력"
        row = expense_df.loc[i]
        d = row.get("날짜")
        date_txt = d.isoformat() if hasattr(d, "isoformat") else str(d)
        usage = row.get("적요") or ""
        item = row.get("지출항목") or ""
        detail = row.get("지출내역") or ""
        amount = row.get("금액")
        amt_txt = f"{int(amount):,}" if pd.notna(amount) else ""
        note = row.get("비고") or ""
        return f"{date_txt} / {usage} / {item} / {detail} / {amt_txt} / {note}"
    expense_edit_idx = st.selectbox(
        "수정할 지출 행",
        options=[-1] + list(expense_df.index),
        format_func=_expense_label,
        key="expense_edit_idx",
    )
    if "expense_form_date" not in st.session_state:
        _reset_expense_form()
    if st.session_state.get("expense_edit_last") != expense_edit_idx:
        st.session_state["expense_edit_last"] = expense_edit_idx
        if expense_edit_idx in expense_df.index:
            expense_row = expense_df.loc[expense_edit_idx]
            st.session_state["expense_form_date"] = _coerce_date(expense_row.get("날짜"), selected_date)
            usage = expense_row.get("적요")
            if usage not in USAGE_OPTIONS:
                usage = USAGE_OPTIONS[0]
            st.session_state["expense_form_usage"] = usage
            item = expense_row.get("지출항목")
            if item not in EXPENSE_ITEMS:
                item = EXPENSE_ITEMS[0]
            st.session_state["expense_form_item"] = item
            st.session_state["expense_form_detail"] = _coerce_text(expense_row.get("지출내역"))
            st.session_state["expense_form_amount"] = _coerce_amount(expense_row.get("금액"))
            st.session_state["expense_form_note"] = _coerce_text(expense_row.get("비고"))
        else:
            _reset_expense_form()
    with st.form("expense_form", clear_on_submit=False):
        c1, c2 = st.columns(2, gap="small")
        ex_date = c1.date_input("날짜", key="expense_form_date")
        ex_usage = c2.selectbox("적요", USAGE_OPTIONS, key="expense_form_usage")
        ex_item = st.selectbox("지출항목", EXPENSE_ITEMS, key="expense_form_item")
        ex_detail = st.text_input("지출내역", key="expense_form_detail")
        ex_amount = st.number_input("금액(원)", min_value=0, step=1, key="expense_form_amount")
        ex_note = st.text_input("비고", key="expense_form_note")
        expense_submit = st.form_submit_button("지출 저장")
    if expense_submit:
        _upsert_row(
            "expense",
            None if expense_edit_idx == -1 else expense_edit_idx,
            {
                "날짜": ex_date,
                "적요": ex_usage,
                "지출항목": ex_item,
                "지출내역": ex_detail,
                "금액": ex_amount,
                "비고": ex_note,
            },
        )
        st.session_state["expense_edit_idx"] = -1
        st.session_state["expense_edit_last"] = -1
        _reset_expense_form()
        st.toast("지출 항목을 저장했습니다.", icon="✅")
        st.rerun()
    st.dataframe(expense_df, width="stretch", hide_index=True)

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
