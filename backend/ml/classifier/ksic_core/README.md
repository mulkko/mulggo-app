# KSIC 업종매칭 — 백엔드 연동 패키지 (Pipeline V2.x, Frozen)

## 진입점

```python
from ksic_core.predict import predict

result = predict(text)  # text: 공고 원문(지원대상/신청자격 등)
```

단일 진입점. 입출력 스키마는 변경되지 않았습니다(`PIPELINE_V2X_FINAL_FREEZE.md` 참고,
필요하면 원본 프로젝트에서 함께 전달).

## 설치

```
pip install -r requirements.txt
```

`.env.example`을 `.env`로 복사한 뒤 실제 `OPENAI_API_KEY` 값을 채워 넣으세요.
(`LLM_PROVIDER`, `GOOGLE_API_KEY`, `DEBUG_LLM`은 기본값 openai를 쓰면 비워둬도 됩니다.)

## 폴더 구성

- `ksic_core/` — 매칭 로직 전체(Rule → Whitelist → ML Gate → Resolver/Verifier → predict).
  테스트 파일(`test_*.py`)도 포함되어 있어 `python -m unittest discover ksic_core`로
  회귀 검증이 가능합니다.
- `models/` — ML Gate 아티팩트. 현재 로드되는 것은 `ml_gate_v2_champion.joblib`이며,
  나머지(`ml_gate_v1_baseline.joblib`, `ml_gate_v2_challenger_B.joblib`)는 롤백/비교용으로
  같이 넣었습니다(삭제해도 predict() 동작에는 지장 없음).
- `data/` — `ksic_core`가 런타임에 실제로 읽는 참조 테이블만 추려서 원래와 동일한
  상대경로로 넣었습니다(KSIC 코드표, 색인어 사전, 제외업종 목록, 신구코드 크로스워크,
  해설서 요약, ML Gate v1 원본).

## Smoke test (LLM 미호출)

```
python -c "from ksic_core.predict import predict; from ksic_core import ml_gate_runtime; ml_gate_runtime._load_artifact(); print('gate ok' if ml_gate_runtime._artifact else ml_gate_runtime._load_error)"
```

## 주의

- `predict()`는 애매한 케이스에서 실제 LLM(OpenAI) API를 호출합니다 — `OPENAI_API_KEY` 필요.
- 모델/규칙 로직은 이 폴더로 옮기면서 전혀 수정하지 않았습니다(원본 프로젝트와 100% 동일).
