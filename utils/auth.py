# -*- coding: utf-8 -*-
import streamlit as st
from dataclasses import dataclass

@dataclass(frozen=True)
class AdminCredential:
    username: str
    password: str

# 허용 계정(요구사항)
ALLOWED_ADMINS = [
    AdminCredential(username="heiakak", password="dl2tk4vkF*"),
    AdminCredential(username="평안한", password="0560"),
]

def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated", False))

def authenticate(username: str, password: str) -> bool:
    # 간단 인증(요구사항). 실제 운영 시에는 환경변수/해시/SSO 등을 권장합니다.
    u = (username or "").strip()
    p = password or ""
    return any((u == adm.username and p == adm.password) for adm in ALLOWED_ADMINS)

def login_form() -> None:
    st.subheader("로그인")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("ID", placeholder="아이디를 입력하세요", autocomplete="username")
        password = st.text_input("PW", type="password", placeholder="비밀번호를 입력하세요", autocomplete="current-password")
        submitted = st.form_submit_button("로그인", width="stretch")

    if submitted:
        if authenticate(username.strip(), password):
            st.session_state["authenticated"] = True
            st.toast("로그인 완료", icon="✅")
            # 페이지 새로고침
            st.rerun()
        else:
            st.error("ID 또는 PW가 올바르지 않습니다.")

def logout_button(key: str = "logout_btn") -> None:
    if st.button("로그아웃", key=key, width="stretch"):
        st.session_state["authenticated"] = False
        st.toast("로그아웃 됨", icon="👋")
        st.rerun()

def require_login() -> bool:
    if not is_authenticated():
        st.warning("로그인이 필요합니다. 상단 메뉴에서 '기본정보'로 이동해 로그인해 주세요.")
        try:
            st.page_link("app.py", label="➡️ 기본정보(로그인)로 이동", icon="🔐")
        except Exception:
            if st.button("기본정보(로그인)로 이동", type="primary", width="stretch", key="go_login_btn"):
                try:
                    st.switch_page("app.py")
                except Exception:
                    pass
        return False
    return True
