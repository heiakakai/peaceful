# -*- coding: utf-8 -*-
import os
import sqlite3
import datetime as dt
from typing import Tuple
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "church_finance.db")

INCOME_COLS = ["날짜", "적요", "수입항목", "수입내역", "금액", "비고"]
EXPENSE_COLS = ["날짜", "적요", "지출항목", "지출내역", "금액", "비고"]

def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db() -> None:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            d TEXT NOT NULL,
            usage TEXT,
            item TEXT,
            detail TEXT,
            amount REAL,
            note TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expense (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            d TEXT NOT NULL,
            usage TEXT,
            item TEXT,
            detail TEXT,
            amount REAL,
            note TEXT
        )
    """)
    conn.commit()
    conn.close()

def _normalize_amount(x):
    if x is None:
        return None
    try:
        if isinstance(x, str):
            x = x.replace(",", "").strip()
            if x == "":
                return None
        return float(x)
    except Exception:
        return None

def _clean_df(df: pd.DataFrame, cols) -> pd.DataFrame:
    # 필요한 컬럼만 유지 + 순서 고정
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]

    # 날짜 보정
    def to_date(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        if isinstance(v, dt.date):
            return v
        if isinstance(v, dt.datetime):
            return v.date()
        # 문자열 파싱
        try:
            return pd.to_datetime(v).date()
        except Exception:
            return None

    df["날짜"] = df["날짜"].apply(to_date)

    # 금액 보정
    df["금액"] = df["금액"].apply(_normalize_amount)

    # 완전 빈 행 제거(내역/금액/비고 모두 비면 제거)
    nonempty = df[["금액"]].notna().any(axis=1) | df.iloc[:, 0:].fillna("").astype(str).apply(lambda r: any(s.strip() for s in r.values), axis=1)
    # 위 조건이 너무 넓게 잡힐 수 있어, 핵심 컬럼 기반으로 다시 좁힘
    # income: 수입내역 or 금액 or 수입항목 중 하나라도 있으면 유지
    if "수입내역" in df.columns:
        nonempty = df["수입내역"].fillna("").astype(str).str.strip().ne("") | df["금액"].notna() | df["수입항목"].fillna("").astype(str).str.strip().ne("")
    if "지출내역" in df.columns:
        nonempty = df["지출내역"].fillna("").astype(str).str.strip().ne("") | df["금액"].notna() | df["지출항목"].fillna("").astype(str).str.strip().ne("")
    df = df.loc[nonempty].reset_index(drop=True)

    return df


def fetch_range(start_date: dt.date, end_date: dt.date) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """start_date ~ end_date(포함) 범위의 수입/지출 데이터를 반환합니다."""
    init_db()
    conn = _connect()
    sd = start_date.isoformat()
    ed = end_date.isoformat()

    income = pd.read_sql_query(
        "SELECT d as 날짜, usage as 적요, item as 수입항목, detail as 수입내역, amount as 금액, note as 비고 "
        "FROM income WHERE d >= ? AND d <= ? ORDER BY d, id",
        conn,
        params=(sd, ed),
    )
    expense = pd.read_sql_query(
        "SELECT d as 날짜, usage as 적요, item as 지출항목, detail as 지출내역, amount as 금액, note as 비고 "
        "FROM expense WHERE d >= ? AND d <= ? ORDER BY d, id",
        conn,
        params=(sd, ed),
    )
    conn.close()

    # 날짜 컬럼을 date로
    if not income.empty:
        income["날짜"] = pd.to_datetime(income["날짜"]).dt.date
    if not expense.empty:
        expense["날짜"] = pd.to_datetime(expense["날짜"]).dt.date

    # 컬럼 정리/정규화
    income = _clean_df(income, INCOME_COLS)
    expense = _clean_df(expense, EXPENSE_COLS)
    return income, expense

def fetch_day(d: dt.date) -> Tuple[pd.DataFrame, pd.DataFrame]:
    init_db()
    conn = _connect()
    ds = d.isoformat()

    income = pd.read_sql_query(
        "SELECT d as 날짜, usage as 적요, item as 수입항목, detail as 수입내역, amount as 금액, note as 비고 FROM income WHERE d=? ORDER BY id",
        conn, params=(ds,)
    )
    expense = pd.read_sql_query(
        "SELECT d as 날짜, usage as 적요, item as 지출항목, detail as 지출내역, amount as 금액, note as 비고 FROM expense WHERE d=? ORDER BY id",
        conn, params=(ds,)
    )
    conn.close()

    # 날짜 컬럼을 date로
    if not income.empty:
        income["날짜"] = pd.to_datetime(income["날짜"]).dt.date
    if not expense.empty:
        expense["날짜"] = pd.to_datetime(expense["날짜"]).dt.date

    # 컬럼 정리
    income = _clean_df(income, INCOME_COLS)
    expense = _clean_df(expense, EXPENSE_COLS)

    return income, expense

def save_day(d: dt.date, income_df: pd.DataFrame, expense_df: pd.DataFrame) -> None:
    init_db()
    conn = _connect()
    cur = conn.cursor()
    ds = d.isoformat()

    income_df = _clean_df(income_df, INCOME_COLS)
    expense_df = _clean_df(expense_df, EXPENSE_COLS)

    # 날짜가 비어 있으면 선택일자로 채움
    income_df.loc[income_df["날짜"].isna(), "날짜"] = d
    expense_df.loc[expense_df["날짜"].isna(), "날짜"] = d

    # 선택일자 외 날짜가 들어오면 그대로 저장(하지만 이 페이지는 선택일자 중심이므로 경고를 원하면 추가 가능)
    # 저장은 단순화를 위해: 선택일자 레코드 전체 삭제 후 재삽입
    cur.execute("DELETE FROM income WHERE d=?", (ds,))
    cur.execute("DELETE FROM expense WHERE d=?", (ds,))

    for _, r in income_df.iterrows():
        cur.execute(
            "INSERT INTO income (d, usage, item, detail, amount, note) VALUES (?, ?, ?, ?, ?, ?)",
            (
                (r["날짜"].isoformat() if hasattr(r["날짜"], "isoformat") else ds),
                (r["적요"] if pd.notna(r["적요"]) else None),
                (r["수입항목"] if pd.notna(r["수입항목"]) else None),
                (r["수입내역"] if pd.notna(r["수입내역"]) else None),
                (float(r["금액"]) if pd.notna(r["금액"]) else None),
                (r["비고"] if pd.notna(r["비고"]) else None),
            )
        )

    for _, r in expense_df.iterrows():
        cur.execute(
            "INSERT INTO expense (d, usage, item, detail, amount, note) VALUES (?, ?, ?, ?, ?, ?)",
            (
                (r["날짜"].isoformat() if hasattr(r["날짜"], "isoformat") else ds),
                (r["적요"] if pd.notna(r["적요"]) else None),
                (r["지출항목"] if pd.notna(r["지출항목"]) else None),
                (r["지출내역"] if pd.notna(r["지출내역"]) else None),
                (float(r["금액"]) if pd.notna(r["금액"]) else None),
                (r["비고"] if pd.notna(r["비고"]) else None),
            )
        )

    conn.commit()
    conn.close()

def fetch_all() -> Tuple[pd.DataFrame, pd.DataFrame]:
    init_db()
    conn = _connect()
    income = pd.read_sql_query(
        "SELECT d as 날짜, usage as 적요, item as 수입항목, detail as 수입내역, amount as 금액, note as 비고 FROM income ORDER BY d, id",
        conn
    )
    expense = pd.read_sql_query(
        "SELECT d as 날짜, usage as 적요, item as 지출항목, detail as 지출내역, amount as 금액, note as 비고 FROM expense ORDER BY d, id",
        conn
    )
    conn.close()
    if not income.empty:
        income["날짜"] = pd.to_datetime(income["날짜"]).dt.date
    if not expense.empty:
        expense["날짜"] = pd.to_datetime(expense["날짜"]).dt.date
    income = _clean_df(income, INCOME_COLS)
    expense = _clean_df(expense, EXPENSE_COLS)
    return income, expense
