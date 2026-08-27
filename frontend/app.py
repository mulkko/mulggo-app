import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.connection import get_connection

st.set_page_config(page_title="mulkko", page_icon="🌊")

st.title("mulkko")
st.write("사업구체화 · 정부지원사업 매칭 · 성장 로드맵 어시스턴트")
st.info("서비스 준비 중입니다. 기능이 추가되는 대로 이 화면이 업데이트됩니다.")

st.subheader("test_table 조회")

try:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM test_table")
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=columns)
        st.dataframe(df)
    finally:
        connection.close()
except Exception as e:
    st.error(f"test_table 조회 실패: {e}")
