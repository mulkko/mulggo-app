"""ksic_core(Pipeline V2.x, Frozen) 백엔드 연동 진입점.

[2026-09-13] E:\\3차프로젝트\\매칭기능_백엔드에서 그대로 복사해온 완성본(ksic_core/,
models/, data/ — 전부 이 파일과 같은 디렉터리에 나란히 둠, 원본 파일 자체는 한 글자도
수정하지 않음, PIPELINE_V2X_FINAL_FREEZE.md 참고). 아직 실제 호출부에는 연결하지
않았다 — 이 모듈이 기존 backend/ml/classifier/decide_industry.py(공고 원문 -> KSIC
규칙+LLM 매칭, backend/preprocessing/pipeline.py가 실사용 중)의 최종 완성본이 맞는지,
그 자리에 실제로 바꿔 끼울지는 사용자 확인 후 진행하기로 함 - 이 파일은 "어떻게
연결하면 되는지"에 대한 준비된 답만 코드로 남겨둔 것.

ksic_core 내부는 전부 `from ksic_core.xxx import yyy` 절대 임포트라서, 최상위
패키지로 인식되려면 부모 디렉터리(이 파일이 있는 backend/ml/classifier/)가
sys.path에 먼저 들어가 있어야 한다 - industry_code_matching/service.py가 industry_matcher를
불러올 때 쓰는 것과 동일한 패턴(그쪽 주석 참고). ksic_core 폴더 안 코드는 그 프로젝트와
마찬가지로 여기서도 손대지 않는다.

사용법:
    from backend.ml.classifier.ksic_core_service import predict_from_notice_text
    result = predict_from_notice_text(공고_원문)
    # result["service_category"]: "특정업종대상" | "전업종노출"
    # result["ksic_codes"] / result["ksic_names"]: 확정 KSIC
    # 전체 스키마는 ksic_core/predict.py의 predict() 문서 참고.

주의: predict()는 애매한 케이스에서 실제 LLM(OpenAI) API를 호출한다 - .env의
OPENAI_API_KEY/LLM_PROVIDER(기존 backend/ml/classifier/llm_match.py와 같은 변수,
.env.example 참고)를 그대로 재사용하므로 새 환경변수는 필요 없다.
ML Gate(임베딩)는 scipy/sentence-transformers/torch/joblib/kiwipiepy가 추가로
필요하다 - 아직 requirements.txt에 반영 안 함(사용자 확인 후 추가 예정).
"""
from __future__ import annotations

import sys
from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from ksic_core.predict import predict as predict_from_notice_text  # noqa: E402

__all__ = ["predict_from_notice_text"]
