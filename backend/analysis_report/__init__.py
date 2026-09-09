# 분석 리포트 (마이페이지 "나의 분석 리포트" / 매칭 리스트 "물꼬 분석" 화면의 배경 로직)
# 담당: 데이터 분석 (DA)
#
# 원래 Jupyter 노트북(분석 리포트_상권/, 분석 리포트_기술 창업/)에서 실제 데이터로
# 검증까지 끝난 함수들을 코딩 컨벤션(영문 snake_case)에 맞춰 정식 모듈로 옮긴 것.
# 원본 노트북(실행결과 삭제 후)은 notebooks/ 아래에 그대로 보관 — 검증 과정과
# 시각화 코드는 여기 옮기지 않았으니 참고할 땐 그쪽을 본다.
#
#   market/        상권 분석 (상주인구·유동인구, 인근 업종 분포, 반경 내 동일업종 밀집도)
#   tech_startup/  기술창업 분석 (유사 벤처기업/투자유형, 특허 시계열 예측)
#
# [2026-09-09 기준] backend/api/analysis.py 가 이 함수들을 호출하는 라우터고
# main.py에도 등록돼 있다(/analysis/market, /analysis/tech-startup,
# /analysis/patent-startup). 데이터 소스는 DB로 확정 — commercial_districts만
# 크기(270만 건) 때문에 별도 분석용 DB(get_analysis_connection())에 있고
# 나머지 4개 테이블은 메인 DB에 있다(적재는 backend/db/load_analysis_data.py).
# 이 파일들의 함수는 여전히 DataFrame을 인자로 받는 순수함수 그대로다 —
# analysis.py가 DB에서 읽은 결과를 DataFrame으로 실어 나르기만 하고, 판단
# 로직은 안 건드린다.
#
# [남은 일] 지금 이 API를 실제로 부르는 곳은 frontend/dev/analysis-test.html
# (개발용 테스트 페이지)뿐이다. 원래 목적인 마이페이지 "나의 분석 리포트" /
# 매칭 리스트 "물꼬 분석" 실제 화면(frontend/src/pages)엔 아직 연동 안 됨.
