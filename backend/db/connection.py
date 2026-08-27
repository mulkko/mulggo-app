# Oracle DB 연결 모듈
# .env의 DB_HOST, DB_PORT, DB_SERVICE, DB_USER, DB_PASSWORD로 접속한다.
# cx_Oracle은 항상 로컬에 설치된 Oracle Client(OCI)를 통해 접속하므로
# 현재 설치된 11.2 클라이언트로도 접속할 수 있다.

import os
import oracledb
from dotenv import load_dotenv
import streamlit as st

# 1. 환경 변수 로드
load_dotenv()

# 2. ★ 핵심: 오라클 11g 접속을 위해 코드가 읽히자마자 가장 먼저 Thick 모드 활성화!
try:
    oracledb.init_oracle_client(lib_dir=r"D:\project_file\instantclient_19_32")
except Exception as e:
    # 이미 초기화되었거나 잡혀있는 경우 무시
    pass

# DB_HOST = os.getenv("DB_HOST")
# DB_PORT = os.getenv("DB_PORT")
# DB_SERVICE = os.getenv("DB_SERVICE")
# DB_USER = os.getenv("DB_USER")
# DB_PASSWORD = os.getenv("DB_PASSWORD")

DB_HOST = st.secrets.get("DB_HOST") or os.getenv("DB_HOST")
DB_PORT = st.secrets.get("DB_PORT") or os.getenv("DB_PORT")
DB_SERVICE = st.secrets.get("DB_SERVICE") or os.getenv("DB_SERVICE")
DB_USER = st.secrets.get("DB_USER") or os.getenv("DB_USER")
DB_PASSWORD = st.secrets.get("DB_PASSWORD") or os.getenv("DB_PASSWORD")


def get_connection():
    if not all([DB_HOST, DB_PORT, DB_SERVICE, DB_USER, DB_PASSWORD]):
        raise RuntimeError(
            "DB_HOST, DB_PORT, DB_SERVICE, DB_USER, DB_PASSWORD가 .env에 설정되어 있지 않습니다."
        )

    # DSN 생성 및 Thick 모드로 접속
    dsn = oracledb.makedsn(DB_HOST, DB_PORT, service_name=DB_SERVICE)
    return oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=dsn)


if __name__ == "__main__":
    connection = None
    try:
        connection = get_connection()
        print("연결 성공!")
    except Exception as e:
        print(f"연결 실패: {e}")
    finally:
        if connection:
            connection.close()
