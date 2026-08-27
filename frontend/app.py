import oracledb

# 구버전 오라클 DB와 연동하기 위해 Thick 모드 활성화 (경로는 본인 PC/서버 환경에 맞게)
# 스트림릿 클라우드에서는 보통 기본 설정으로 동작하거나 아래와 같이 호출합니다.
oracledb.init_oracle_client()

import streamlit as st

st.set_page_config(page_title="mulkko", page_icon="🌊")

st.title("mulkko")
st.write("사업구체화 · 정부지원사업 매칭 · 성장 로드맵 어시스턴트")
st.info("서비스 준비 중입니다. 기능이 추가되는 대로 이 화면이 업데이트됩니다.")
