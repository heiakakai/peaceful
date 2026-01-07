# -*- coding: utf-8 -*-
import datetime as dt
import calendar
import streamlit as st

from utils.auth import is_authenticated, logout_button
from utils.storage import fetch_all
from utils.exporter import export_all_xlsx

def apply_global_style() -> None:
    # 중년층 친화: 큰 글씨, 넓은 버튼, 여백 확보
    # 상단바 네비게이션을 쓰기 위해 사이드바는 숨김
    st.markdown(
        """
        <style>
        html, body, [class*="css"]  { font-size: 18px !important; }
        .block-container { padding-top: 1.4rem; padding-bottom: 2.2rem; }
        section[data-testid="stSidebar"] { display: none !important; }

        /* Streamlit 상단 상태바/툴바가 상단 메뉴를 가리는 문제 방지 */
        header[data-testid="stHeader"] { display: none !important; }
        div[data-testid="stToolbar"] { display: none !important; }
        div[data-testid="stDecoration"] { display: none !important; }

        button[kind="primary"], button[kind="secondary"] { min-height: 44px; font-size: 18px; }
        input, textarea, select { font-size: 18px !important; }
        div[data-testid="stDataFrame"] { font-size: 17px; }

        .big-title { font-size: 30px; font-weight: 800; margin-bottom: 0.25rem; }
        .sub-title { font-size: 18px; color: rgba(49, 51, 63, 0.7); margin-bottom: 0.8rem; }

        /* metric 폰트(합계 금액 등) 절반 수준으로 축소 */
        div[data-testid="stMetricValue"] { font-size: 1.25rem !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.95rem !important; }

        /* 제목 오른쪽 '링크' 아이콘(헤더 앵커) 숨김 */
        [data-testid="stHeaderActionElements"] { display: none !important; }

        /* 섹션 타이틀 */
        .section-title { font-size: 20px; font-weight: 800; margin: 0.2rem 0 0.3rem 0; }


        /* 상단 네비게이션 간격 */
        .topnav { margin-bottom: 0.6rem; }
        /* 상단 버튼이 상단에 붙어 깔리는 것 방지 */
        div[data-testid="stHorizontalBlock"]:has(button[key^="nav_"]) { padding-top: 0.2rem; }

        </style>
        """,
        unsafe_allow_html=True,
    )

def render_header(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="big-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="sub-title">{subtitle}</div>', unsafe_allow_html=True)

def render_top_nav(active: str) -> None:
    """
    상단바 네비게이션(사이드바 대신).
    active: 현재 페이지 키 (e.g., "기본정보", "재정장부(입력)")
    """

    # 페이지 이동(진입) 감지: 다른 페이지에서 넘어왔을 때 visit 카운트를 증가
    prev_active = st.session_state.get("__active_page")
    if prev_active != active:
        st.session_state[f"__visit_{active}"] = int(st.session_state.get(f"__visit_{active}", 0)) + 1
    st.session_state["__active_page"] = active

    st.markdown('<div class="topnav"></div>', unsafe_allow_html=True)

    pages = [
        ("기본정보", "app.py"),
        ("재정장부(입력)", "pages/1_재정장부_입력.py"),
        ("재정장부(보고)", "pages/2_재정장부_보고.py"),
        ("월별 현황(수입)", "pages/3_월별현황_수입.py"),
        ("월별 현황(지출)", "pages/4_월별현황_지출.py"),
        ("예산안", "pages/6_예산안.py"),
    ]

    # 버튼을 가로로 배치
    cols = st.columns([1, 1, 1, 1, 1, 0.9, 1.35], gap="small")
    for i, (label, path) in enumerate(pages):
        btn_type = "primary" if label == active else "secondary"
        if cols[i].button(label, type=btn_type, key=f"nav_{active}_{label}", width="stretch"):
            try:
                st.switch_page(path)
            except Exception:
                st.info("페이지 이동 기능을 사용할 수 없습니다. Streamlit 버전을 확인해 주세요.")
    # 오른쪽: 로그인/로그아웃 + 엑셀 다운로드
    with cols[-1]:
        if is_authenticated():
            logout_button(key=f"logout_{active}")
            # 전체 엑셀 다운로드
            try:
                income_all, expense_all = fetch_all()
                xlsx_bytes = export_all_xlsx(income_all, expense_all)
                st.download_button(
                    "전체 엑셀(.xlsx)",
                    data=xlsx_bytes,
                    file_name=f"교회재정_전체데이터_{dt.date.today().isoformat()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    key=f"dl_all_{active}",
                )
            except Exception as e:
                st.caption("전체 엑셀 준비 실패")
        else:
            # 캡션을 빼고 버튼만 표시(두 줄로 보이는 문제 방지)
            if st.button("🔐 로그인", type="primary", key=f"nav_login_btn_{active}", width="stretch"):
                try:
                    st.switch_page("app.py")
                except Exception:
                    pass
def _sundays_of_month(year: int, month: int):
    cal = calendar.monthcalendar(year, month)
    sundays = []
    for week in cal:
        d = week[calendar.SUNDAY]
        if d != 0:
            sundays.append(dt.date(year, month, d))
    return sundays

def church_date_picker(prefix: str = "date") -> dt.date:
    """
    교회 장부용 날짜 선택기(안정화 버전):
    - 년/월 선택
    - 주일(일요일) 선택이 기본
    - 아래에서 1~말일까지 '일' 직접 선택 가능
    - 페이지 이동/년월 변경 시 기본값을 '현재 날짜 기준 가장 가까운 과거 주일'로 초기화
    - 표 입력(재실행) 중에도 '일' 선택이 주일로 갑자기 되돌아가지 않도록 안정화
      (주일 값이 실제로 바뀐 경우에만 '일' 위젯을 초기화)
    """
    today = dt.date.today()
    years = list(range(today.year - 5, today.year + 6))

    y_key = f"{prefix}_y"
    m_key = f"{prefix}_m"

    c1, c2 = st.columns([1, 1], gap="small")
    year = c1.selectbox("년", years, index=years.index(today.year), key=y_key)
    month = c2.selectbox("월", list(range(1, 13)), index=today.month - 1, key=m_key)

    sundays = _sundays_of_month(year, month)
    if not sundays:
        sundays = [dt.date(year, month, 1)]

    # 기본 주일(오늘이 주일이면 오늘, 아니면 오늘 이전 가장 가까운 주일, 없으면 첫 주일)
    default_sunday = sundays[0]
    if year == today.year and month == today.month:
        if today.weekday() == 6 and today in sundays:
            default_sunday = today
        else:
            past = [d for d in sundays if d <= today]
            if past:
                default_sunday = past[-1]

    active_page = st.session_state.get("__active_page", "")
    visit_id = int(st.session_state.get(f"__visit_{active_page}", 0))
    visit_key = f"{prefix}_visit_id"
    ym_key = f"{prefix}_ym"
    ym_val = f"{year:04d}-{month:02d}"

    sun_key = f"{prefix}_sunday"
    day_key = f"{prefix}_day"
    last_sun_key = f"{prefix}_last_sun"

    needs_reset = False
    if st.session_state.get(visit_key) != visit_id:
        st.session_state[visit_key] = visit_id
        needs_reset = True
    if st.session_state.get(ym_key) != ym_val:
        st.session_state[ym_key] = ym_val
        needs_reset = True

    if needs_reset:
        st.session_state.pop(sun_key, None)
        st.session_state.pop(day_key, None)
        st.session_state.pop(last_sun_key, None)

    # 주일 위젯: dt.date 객체 대신 ISO 문자열로 옵션을 구성(동등성/변경감지 안정화)
    sundays_iso = [d.isoformat() for d in sundays]
    default_sun_iso = default_sunday.isoformat()
    default_sun_idx = sundays_iso.index(default_sun_iso) if default_sun_iso in sundays_iso else 0

    def _fmt_sun(iso: str) -> str:
        try:
            d = dt.date.fromisoformat(iso)
        except Exception:
            return iso
        idx = sundays.index(d) + 1 if d in sundays else 1
        return f"{idx}주차 주일 ({d.month}월 {d.day}일)"

    # 현재 값이 옵션에 없으면 초기화
    if sun_key in st.session_state and st.session_state[sun_key] not in sundays_iso:
        st.session_state.pop(sun_key, None)

    selected_sun_iso = st.selectbox(
        "주일(일요일) 선택(기본)",
        options=sundays_iso,
        index=default_sun_idx,
        format_func=_fmt_sun,
        key=sun_key,
    )
    selected_sunday = dt.date.fromisoformat(selected_sun_iso)

    # 주일이 실제로 변경된 경우에만 '일'을 주일 날짜로 초기화(pop)
    prev_sun_iso = st.session_state.get(last_sun_key)
    if prev_sun_iso is not None and prev_sun_iso != selected_sun_iso:
        st.session_state.pop(day_key, None)
    st.session_state[last_sun_key] = selected_sun_iso

    last_day = calendar.monthrange(year, month)[1]
    days = list(range(1, last_day + 1))
    default_day = selected_sunday.day

    # 세션에 저장된 day가 있으면 그 값을 우선(사용자 직접 선택 유지)
    if day_key in st.session_state:
        try:
            v = int(st.session_state[day_key])
            if 1 <= v <= last_day:
                default_day = v
            else:
                st.session_state.pop(day_key, None)
        except Exception:
            st.session_state.pop(day_key, None)

    selected_day = st.selectbox(
        "일(1~말일) 직접 선택",
        options=days,
        index=days.index(default_day),
        key=day_key,
        help="기본은 주일(일요일)입니다. 필요하면 다른 날짜를 선택하세요.",
    )

    return dt.date(year, month, int(selected_day))
