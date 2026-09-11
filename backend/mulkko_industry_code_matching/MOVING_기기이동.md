# 다른 컴퓨터로 옮길 때

이 zip **하나만** 가져가면 됩니다. 코드 + 벡터 DB + 데이터 전부 들어 있습니다.

## 새 컴퓨터에서 할 일 (순서대로)

```bash
# 1) 압축 풀기
unzip mulkko_industry_code_matching_20260909.zip
cd mulkko_industry_code_matching

# 2) 파이썬 3.10 이상 + 패키지 설치
pip install -r requirements.txt
#   (openai, chromadb, pandas, python-dotenv)

# 3) .env 만들기  ← zip에는 없음 (보안). 직접 만들어야 함
cp .env.example .env
#   .env 를 열어서 아래 3줄 채우기:
#     OPENAI_API_KEY=sk-...        ← 본인 키 (크레딧 있어야 함)
#     LLM_MODEL=gpt-5-mini
#     EMBEDDING_MODEL=text-embedding-3-small

# 4) 상태 점검
python -c "from industry_matcher import health; print(health())"
#   -> chroma_doc_count 14627, reference_rows 1612 나오면 정상

# 5) 한 건 테스트 (크레딧 소모됨)
python business_matching/23_match_business_code_v3.py \
  --seed "직접 볶은 원두로 매장에서 커피 음료를 만들어 손님에게 판매하는 카페를 운영한다" \
  --problem "동네에 제대로 된 스페셜티 커피를 마실 곳이 없다는 불편이 크다" \
  --solution "좌석을 갖춘 매장에서 바리스타가 에스프레소 음료를 제조해 현장에서 판매한다"
```

## 체크리스트

- [ ] 압축을 풀었을 때 `business_matching/`, `data/`, `chroma_db/` 폴더가 그대로 있는가
- [ ] `pip install -r requirements.txt` 성공했는가
- [ ] `.env` 에 **작동하는** `OPENAI_API_KEY` 를 넣었는가 (크레딧 잔액 확인: platform.openai.com/settings/organization/billing)
- [ ] `health()` 가 `chroma_doc_count 14627` 을 반환하는가
- [ ] 파이썬 3.10 이상인가

## 자주 나는 문제

| 증상 | 원인 / 해결 |
|---|---|
| `RuntimeError: OPENAI_API_KEY가 없습니다` | `.env` 파일이 없거나 키가 비어 있음 |
| `429 insufficient_quota / no credits remaining` | OpenAI 크레딧 0. 충전 필요 |
| `chroma_doc_count` 가 0 또는 에러 | `chroma_db/business_code_docs_2025/` 폴더가 압축 풀 때 누락됨. zip 다시 확인 |
| `Embedding 모델 불일치` 에러 | `.env` 의 `EMBEDDING_MODEL` 이 `text-embedding-3-small` 이 아님 (DB가 그 모델로 만들어짐) |
| import 에러 (chromadb 등) | `pip install -r requirements.txt` 안 됨 / 파이썬 버전 낮음 |

## 안 가져가도 되는 것

- `.env` (본인 키는 새 컴퓨터에서 직접) — 절대 키를 공유 zip에 넣지 말 것
- `data/outputs/` 안의 평가 결과 (없어도 됨, 재평가하면 다시 생김)

## 문서

- `README.md` — 백엔드 통합 계약 상세
- `CHANGELOG_20260909.md` — 이번 판 변경 내역
- `docs/업종코드매칭_기능_전체브리프.md` — 전체 현황·근거·로드맵
- `docs/business_code_matching_onboarding.html` — 신규 팀원용 (일부 옛 수치 있음, 최신은 브리프 기준)
