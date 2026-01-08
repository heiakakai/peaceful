# -*- coding: utf-8 -*-
import streamlit as st

from utils.ui import apply_global_style, render_header, render_top_nav
from utils.auth import login_form, is_authenticated

st.set_page_config(
    page_title="평안한교회 재정장부",
    page_icon="💒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_global_style()
render_top_nav("기본정보")
render_header("로그인", "로그인 후 모든 메뉴를 확인하고 편집할 수 있습니다. 문의 이사야(010-6776-6789)")

st.write("")

if is_authenticated():
    st.success("로그인 되어 있습니다.")
    st.write("상단 메뉴에서 원하는 항목으로 이동하세요.")
else:
    login_form()
