import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from backend.db.connection import get_connection

st.set_page_config(page_title="mulkko", page_icon="🌊")

st.title("mulkko")
st.write("사업구체화 · 정부지원사업 매칭 · 성장 로드맵 어시스턴트")
st.info("서비스 준비 중입니다. 기능이 추가되는 대로 이 화면이 업데이트됩니다.")

st.subheader("DB 연결 확인")

try:
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute("SELECT table_name FROM user_tables ORDER BY table_name")
        tables = [row[0] for row in cursor.fetchall()]

        st.write(f"테이블 목록 ({len(tables)}개)")
        st.write(tables)

        if tables:
            target_table = tables[0]
            cursor.execute(f"SELECT * FROM {target_table} WHERE ROWNUM = 1")
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()

            st.write(f"[{target_table}] 첫 번째 행")
            if row is None:
                st.write("(데이터 없음)")
            else:
                st.write(dict(zip(columns, row)))
        else:
            st.write("테이블이 없습니다.")
    finally:
        connection.close()
except Exception as e:
    st.error(f"DB 연결 실패: {e}")
