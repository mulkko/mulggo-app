# 회원가입 화면 (구조만 - 스타일링은 추후 적용)
# 가입유형(예비창업자/기존사업자) 선택은 별도 단계에서 처리 예정이라 이 화면에는 포함하지 않는다.

import streamlit as st

st.title("회원가입")

name = st.text_input("이름")
email = st.text_input("아이디(이메일)")
password = st.text_input("비밀번호", type="password")
password_confirm = st.text_input("비밀번호 확인", type="password")
nickname = st.text_input("닉네임")

st.subheader("약관 동의")

agree_all = st.checkbox("전체동의")

col1, col2 = st.columns([4, 1])
with col1:
    agree_terms = st.checkbox("[필수] 서비스 이용약관 동의")
with col2:
    st.page_link("pages/auth/terms.py", label="보기")

col1, col2 = st.columns([4, 1])
with col1:
    agree_privacy = st.checkbox("[필수] 개인정보 수집 및 이용 동의")
with col2:
    st.page_link("pages/auth/privacy.py", label="보기")

st.button("회원가입")
