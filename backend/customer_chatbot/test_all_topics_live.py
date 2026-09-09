"""
고객센터 챗봇 지식 문서 v1의 9개 섹션을 각각 대표 질문으로 실제 AI에 물어보고
답변을 확인하는 스크립트. (mock이 아니라 진짜 OpenAI를 호출합니다)

주피터에서 사용법:
    %run test_all_topics_live.py

주의: 실제 API를 9번 호출하므로 약간의 비용이 발생합니다.
"""

import os
from getpass import getpass

# API 키를 여기서 한 번만 물어보고 환경변수에 저장해서,
# 이후 9번의 호출에서 매번 다시 물어보지 않게 함
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass("OpenAI API 키를 입력하세요 (화면에 안 보입니다): ")

from real_llm_client import call_llm
from customer_service_bot import call_llm_for_customer_support


# 9개 섹션별 대표 질문
TEST_QUESTIONS = [
    ("1. 사업 아이디어 입력", "사업 아이디어는 몇 가지 질문에 답하면 되나요?"),
    ("2. 업종코드 확인", "업종코드는 어떻게 확인되나요?"),
    ("3. 참고용 아이디어 추천", "추천 아이디어를 보면 제 원래 계획이 바뀌나요?"),
    ("4. 지원사업 매칭", "지원사업 필터에는 어떤 항목들이 있나요?"),
    ("5. 분석 리포트", "특허출원 추이는 왜 2025년까지만 나오나요?"),
    ("6. 마이페이지", "마이페이지에서는 뭘 확인할 수 있나요?"),
    ("7. 문의하기", "문의하면 챗봇이 바로 답변을 주나요?"),
    ("8. 회원가입과 사업자등록증 확인", "사업자등록증 인식이 잘 안 되면 어떻게 하나요?"),
    ("9. 신청서 자동입력", "채우기 기능은 어떻게 작동하나요?"),
]


print(f"총 {len(TEST_QUESTIONS)}개 질문 테스트 시작\n" + "=" * 60)

for i, (topic, question) in enumerate(TEST_QUESTIONS, start=1):
    print(f"\n[{topic}]")
    print(f"Q. {question}")

    result = call_llm_for_customer_support(question, llm_client=call_llm)

    print(f"A. {result['answer']}")
    print(f"(문의접수 필요: {result['needs_human_support']})")
    print("-" * 60)

print("\n전체 테스트 완료")
