# 로그인 화면 (구조만 - 스타일링은 추후 적용)

import streamlit as st

st.title("로그인")

email = st.text_input("이메일")
password = st.text_input("비밀번호", type="password")

st.button("로그인")
