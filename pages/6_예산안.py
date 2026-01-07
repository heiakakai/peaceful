# -*- coding: utf-8 -*-
import streamlit as st
from utils.ui import apply_global_style, render_header, render_top_nav
from utils.auth import require_login

st.set_page_config(page_title="예산안", page_icon="📄", layout="wide", initial_sidebar_state="collapsed")
apply_global_style()
render_top_nav("예산안")
render_header("예산안", "추후 구현 예정입니다.")

if not require_login():
    st.stop()

st.info("이 페이지는 현재 빈 페이지입니다. (추후 구현 예정)", icon="🧩")
