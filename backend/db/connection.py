# Supabase(PostgreSQL) 연결 모듈
# .env의 DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD로 접속한다.

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# [2026-09-08] 상권분석용 대용량 참고 데이터(commercial_districts 등) 전용
# 별도 Supabase 프로젝트. 메인 DB 무료 플랜 저장 용량(500MB)을 이 데이터 하나가
# 초과시켜서 분리함 - 자세한 배경은 .env.example 주석 참고.
ANALYSIS_DB_HOST = os.getenv("ANALYSIS_DB_HOST")
ANALYSIS_DB_PORT = os.getenv("ANALYSIS_DB_PORT")
ANALYSIS_DB_NAME = os.getenv("ANALYSIS_DB_NAME")
ANALYSIS_DB_USER = os.getenv("ANALYSIS_DB_USER")
ANALYSIS_DB_PASSWORD = os.getenv("ANALYSIS_DB_PASSWORD")


def get_connection():
    if not all([DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD]):
        raise RuntimeError(
            "DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD가 .env에 설정되어 있지 않습니다."
        )

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def get_analysis_connection():
    """상권분석용 대용량 참고 데이터 전용 DB 연결 (commercial_districts 등).
    메인 DB(get_connection())와 별개 Supabase 프로젝트 - FK로 안 엮여 있어서
    분리 가능했음."""
    if not all([ANALYSIS_DB_HOST, ANALYSIS_DB_PORT, ANALYSIS_DB_NAME, ANALYSIS_DB_USER, ANALYSIS_DB_PASSWORD]):
        raise RuntimeError(
            "ANALYSIS_DB_HOST, ANALYSIS_DB_PORT, ANALYSIS_DB_NAME, ANALYSIS_DB_USER, "
            "ANALYSIS_DB_PASSWORD가 .env에 설정되어 있지 않습니다."
        )

    return psycopg2.connect(
        host=ANALYSIS_DB_HOST,
        port=ANALYSIS_DB_PORT,
        dbname=ANALYSIS_DB_NAME,
        user=ANALYSIS_DB_USER,
        password=ANALYSIS_DB_PASSWORD,
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
