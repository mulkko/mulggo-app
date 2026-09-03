import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.auth.login import login

st.title("관리자 로그인")

email = st.text_input("이메일")
password = st.text_input("비밀번호", type="password")

if st.button("로그인"):
    success, errors = login(email, password)
    if success:
        st.success("로그인 성공")
    else:
        for error in errors:
            st.error(error)
