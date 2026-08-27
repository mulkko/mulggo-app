# Supabase(PostgreSQL) 연결 모듈
# .env(로컬) 또는 st.secrets(Streamlit Cloud)의 DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD로 접속한다.

import os

import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def _get_setting(key: str):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key)


DB_HOST = _get_setting("DB_HOST")
DB_PORT = _get_setting("DB_PORT")
DB_NAME = _get_setting("DB_NAME")
DB_USER = _get_setting("DB_USER")
DB_PASSWORD = _get_setting("DB_PASSWORD")


def get_connection():
    if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        raise RuntimeError(
            "DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD가 .env(또는 st.secrets)에 설정되어 있지 않습니다."
        )

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def list_tables() -> list:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()


if __name__ == "__main__":
    connection = None
    try:
        connection = get_connection()
        print("연결 성공!")
        print("테이블 목록:", list_tables())
    except Exception as e:
        print(f"연결 실패: {e}")
    finally:
        if connection:
            connection.close()
