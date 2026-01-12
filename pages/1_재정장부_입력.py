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
    income_edit_idx = st.selectbox(
        "수정할 수입 행",
        options=[-1] + list(income_df.index),
        format_func=lambda i: "신규 입력" if i == -1 else f"{i + 1}행",
        key="income_edit_idx",
    )
    if income_edit_idx in income_df.index:
        income_row = income_df.loc[income_edit_idx]
        in_date_default = income_row.get("날짜")
        if pd.isna(in_date_default):
            in_date_default = selected_date
        in_usage_default = income_row.get("적요")
        if in_usage_default not in USAGE_OPTIONS:
            in_usage_default = USAGE_OPTIONS[0]
        in_item_default = income_row.get("수입항목")
        if in_item_default not in INCOME_ITEMS:
            in_item_default = INCOME_ITEMS[0]
        in_detail_default = income_row.get("수입내역") or ""
        in_amount_default = income_row.get("금액")
        if pd.isna(in_amount_default):
            in_amount_default = 0
        in_note_default = income_row.get("비고") or ""
    else:
        in_date_default = selected_date
        in_usage_default = USAGE_OPTIONS[0]
        in_item_default = INCOME_ITEMS[0]
        in_detail_default = ""
        in_amount_default = 0
        in_note_default = ""
    with st.form("income_form", clear_on_submit=True):
        c1, c2 = st.columns(2, gap="small")
        in_date = c1.date_input("날짜", value=in_date_default, key=f"in_date_{income_edit_idx}")
        in_usage = c2.selectbox("적요", USAGE_OPTIONS, index=USAGE_OPTIONS.index(in_usage_default), key=f"in_usage_{income_edit_idx}")
        in_item = st.selectbox("수입항목", INCOME_ITEMS, index=INCOME_ITEMS.index(in_item_default), key=f"in_item_{income_edit_idx}")
        in_detail = st.text_input("수입내역", value=in_detail_default, key=f"in_detail_{income_edit_idx}")
        in_amount = st.number_input("금액(원)", min_value=0, step=1, value=in_amount_default, key=f"in_amount_{income_edit_idx}")
        in_note = st.text_input("비고", value=in_note_default, key=f"in_note_{income_edit_idx}")
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
        st.toast("수입 항목을 저장했습니다.", icon="✅")
        st.rerun()
    st.dataframe(income_df, width="stretch", hide_index=True)

with right:
    st.markdown('<div class="section-title">일별 헌금 지출 명세서</div>', unsafe_allow_html=True)
    st.metric("합계 금액", f"₩{expense_total:,.0f}")
    expense_edit_idx = st.selectbox(
        "수정할 지출 행",
        options=[-1] + list(expense_df.index),
        format_func=lambda i: "신규 입력" if i == -1 else f"{i + 1}행",
        key="expense_edit_idx",
    )
    if expense_edit_idx in expense_df.index:
        expense_row = expense_df.loc[expense_edit_idx]
        ex_date_default = expense_row.get("날짜")
        if pd.isna(ex_date_default):
            ex_date_default = selected_date
        ex_usage_default = expense_row.get("적요")
        if ex_usage_default not in USAGE_OPTIONS:
            ex_usage_default = USAGE_OPTIONS[0]
        ex_item_default = expense_row.get("지출항목")
        if ex_item_default not in EXPENSE_ITEMS:
            ex_item_default = EXPENSE_ITEMS[0]
        ex_detail_default = expense_row.get("지출내역") or ""
        ex_amount_default = expense_row.get("금액")
        if pd.isna(ex_amount_default):
            ex_amount_default = 0
        ex_note_default = expense_row.get("비고") or ""
    else:
        ex_date_default = selected_date
        ex_usage_default = USAGE_OPTIONS[0]
        ex_item_default = EXPENSE_ITEMS[0]
        ex_detail_default = ""
        ex_amount_default = 0
        ex_note_default = ""
    with st.form("expense_form", clear_on_submit=True):
        c1, c2 = st.columns(2, gap="small")
        ex_date = c1.date_input("날짜", value=ex_date_default, key=f"ex_date_{expense_edit_idx}")
        ex_usage = c2.selectbox("적요", USAGE_OPTIONS, index=USAGE_OPTIONS.index(ex_usage_default), key=f"ex_usage_{expense_edit_idx}")
        ex_item = st.selectbox("지출항목", EXPENSE_ITEMS, index=EXPENSE_ITEMS.index(ex_item_default), key=f"ex_item_{expense_edit_idx}")
        ex_detail = st.text_input("지출내역", value=ex_detail_default, key=f"ex_detail_{expense_edit_idx}")
        ex_amount = st.number_input("금액(원)", min_value=0, step=1, value=ex_amount_default, key=f"ex_amount_{expense_edit_idx}")
        ex_note = st.text_input("비고", value=ex_note_default, key=f"ex_note_{expense_edit_idx}")
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
