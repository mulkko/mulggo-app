## 작업: 선택 질문 4개(타깃·차별점·수익모델·보유역량) 추가 + 아이디어 카드 생성 실제 연동

**배경**: `pages/diagnosis/*` 5화면(진단방식선택~구체화진단4)은 이미 있음. 이번엔 그 뒤에 "선택 질문" 4개(프로토타입 10-1~10-4, `qMeta.q5`~`q8`)를 이어붙이고, 백엔드에 이미 완성되어 있던 아이디어 카드 생성 기능(`backend/chatbot/idea_card_generator.py` + `real_llm_client.py`)을 실제로 연결한다. **이 두 파일은 손대지 말 것** — 이미 완성된 로직, 그대로 호출만 하면 됨.

**중요 — 업종코드(KSIC) 매칭은 이번 범위에서 제외**: `backend/api/idea_card_test.py`(구 테스트 엔드포인트)엔 `decide_industry()`로 업종코드까지 같이 뽑는 코드가 있지만, 이건 다른 세션이 `ml/industry_code_matching/`에서 임베딩 기반으로 새로 만들고 있는 중(`diagnosisAnswers.ts` 주석에 이미 명시돼 있음) — 여기선 절대 건드리지 말 것. 이번 작업은 **아이디어 카드 생성만** 연결한다.

[레퍼런스] 프로토타입: `C:\workspaces\10_Final\mulggo-app\docs\260910_2008_Mulkko Prototype standalone.html` — 검색 키 `qMeta.q5`~`q8`(재검증 불필요, 아래 실측값 그대로 신뢰).

---

### 1. 흐름 변경 — `DiagnosisStep4.tsx`

지금은 매장형태+지역 선택 후 바로 제출(`/api/diagnosis/submit` 호출 + "제출 완료" 화면)까지 하고 있음. **제출을 뒤로 미루고, 이 화면은 다음 화면으로 넘어가기만 하도록 변경**:

- `handleSubmit`의 fetch/제출 로직, `submitting`/`error`/`submitted` state, "제출 완료" 결과 화면(JSX) 전부 **삭제**하고 아래 5번(`DiagnosisStep8`)로 옮김.
- 버튼 라벨 "제출하기" → "다음", 클릭 시 `saveDiagnosisAnswers({ storeType, sido, sigungu, dong })` 저장 후 `navigate("/diagnosis/5")`.
- `canSubmit` → `canProceed`로 이름만 바꿔도 되고 그대로 둬도 됨(`storeType !== null && sido/sigungu/dong` 조건은 동일).

### 2. `frontend/src/pages/diagnosis/diagnosisAnswers.ts` — 필드 추가

```ts
target?: string;
differentiator?: string;
revenueModel?: string;
coreSkill?: string;
```

### 3. `DiagnosisTextQuestion.tsx` — anchor 힌트박스 + "선택" 모드 지원

- 새 prop `anchor?: string` 추가 — 있으면 textarea 위에 힌트박스 렌더링(아래 4번 스타일).
- 새 prop `required?: boolean`(기본 `true`) 추가 — `false`면 글자수 미만이어도 버튼 비활성화하지 않고 경고문구도 안 띄움(4개 질문은 "선택"이라 빈 값도 허용 — `idea_card_generator.py`가 부실한 슬롯은 알아서 스킵하므로 프론트에서 강제할 필요 없음).

### 4. `diagnosis.module.css` — anchor 힌트박스 스타일 추가

프로토타입 `qAnchor` 실측값 그대로:
- 박스: `background: rgba(21,50,140,.05); border-radius:12px; padding:12px 14px; box-shadow: inset 0 0 0 1.2px rgba(21,50,140,.25); display:flex; gap:8px; align-items:flex-start;`
- 아이콘(반짝임 모양, 15x15, stroke `#15328C` width2): `<path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/>`
- 텍스트: 12.5px, `#15328C`(→ `--color-deep-navy`), line-height1.55, font-weight600

색상은 이미 `--color-deep-navy` 등으로 토큰화돼 있을 가능성 높음 — webTokens.css 확인 후 있으면 재사용, 없으면 추가.

`.resultCard`/`.resultAxis`/`.resultTitle`/`.resultDesc` 클래스는 **이미 diagnosis.module.css에 있음(현재 미사용)** — 5번에서 그대로 씀, 새로 안 만들어도 됨.

### 5. 새 화면 4개 — `DiagnosisStep5~8.tsx` (`/diagnosis/5`~`/diagnosis/8`)

`DiagnosisStep2.tsx`/`DiagnosisStep3.tsx`와 동일 패턴(가드 + `DiagnosisTextQuestion`). **가드는 전부 동일하게** `!answers.sido || !answers.sigungu || !answers.dong`이면 `/diagnosis/4`로 리다이렉트(선택 질문끼리는 서로 값이 비어있을 수 있어서 서로를 가드 조건으로 못 씀 — 직전 필수 단계인 지역 선택 완료 여부만 확인).

| 파일 | 라우트 | slot 키 | stepLabel | anchor | title | sub | placeholder |
|---|---|---|---|---|---|---|---|
| DiagnosisStep5 | /diagnosis/5 | target | 선택 질문 · 1/4 | 유사 벤처인증기업 27개 중 연구개발형이 44%로 가장 많아요. | 이 문제를 가장 크게 겪는 고객층은 누구인가요? | 타깃을 구체적으로 정의할수록 이후 분석·매칭의 정확도가 높아집니다 | 예: 동네 직장인, 재택근무자 |
| DiagnosisStep6 | /diagnosis/6 | differentiator | 선택 질문 · 2/4 | 관련 분야 특허출원이 2021년부터 꾸준히 늘고 있어요. | 기존 대안과 비교해 이 사업만의 차별점은 뭐인가요? | 경쟁 서비스·매장과 비교해 다른 점을 적어주세요 | 예: 프랜차이즈 대비 좌석 여유, 조용함 |
| DiagnosisStep7 | /diagnosis/7 | revenueModel | 선택 질문 · 3/4 | 참고한 우수사례 5건 중 3건이 좌석 이용료+상품 판매 병행 방식을 썼어요. | 어떤 방식으로 수익을 만드실 건가요? | 주요 매출원과 보조 매출원을 구분해 작성해주시면 좋습니다 | 예: 음료 판매, 공간 대여(모임룸) |
| DiagnosisStep8 | /diagnosis/8 | coreSkill | 선택 질문 · 4/4 | (없음) | 이 문제를 해결할 수 있는 본인만의 강점·경험이 있으신가요? | 자격증, 경력, 네트워크 등 구체적으로 작성해주세요 | 예: 바리스타 자격증, 요식업 경력 |

- Step5→6→7→8 순서로 이전/다음 연결. `<DiagnosisTextQuestion required={false} anchor={...} .../>` 로 호출.
- Step5/6/7은 답 저장 후 바로 다음 라우트로 이동(값이 비어있어도 진행 허용).
- **Step8만 다르게 동작** — 아래 6번 참고.

### 6. `DiagnosisStep8.tsx` — 실제 제출 + 카드 결과 표시 (DiagnosisStep4의 옛 제출 로직을 여기로 이식)

- `coreSkill` 답변 입력받은 뒤, 4번에서 옮겨온 `handleSubmit`을 여기서 실행 — `diagnosisAnswers`에 쌓인 전체 답변(origin, seedInterest, problemToSolve, solutionApproach, storeType→hasStore 파생값, sido/sigungu/dong, target, differentiator, revenueModel, 이번 화면의 coreSkill)을 모아 `POST ${API_BASE_URL}/api/diagnosis/submit`에 아래 8번 확장 payload로 전송.
- 성공 시 응답의 `data.cards`를 받아 `submitted` 상태로 전환하고, "제출 완료" 화면(DiagnosisStep4에서 옮겨온 문구/구조 그대로: "사업 구체화가 끝났어요!")에 **카드 리스트 추가 렌더링**:
  ```tsx
  {cards.map((c, i) => (
    <div key={i} className={styles.resultCard}>
      <span className={styles.resultAxis}>{c.axis}</span>
      <span className={styles.resultTitle}>{c.title}</span>
      <span className={styles.resultDesc}>{c.description}</span>
    </div>
  ))}
  ```
  카드가 0개로 올 수도 있음(선택 질문 답변이 다 부실하거나 비어있으면 정상적으로 0개 — 에러 아님) — 이 경우 기존 안내문구("업종코드 매칭·분석 리포트 연결은 준비 중이라...")만 그대로 보여주면 됨.
- 401/서버에러 처리는 DiagnosisStep4에 있던 것 그대로 이식.
- `DiagnosisSubmitResponse` 인터페이스에 `data?: { session_id: number; cards?: { axis: string; title: string; description: string }[] }` 추가.

### 7. `App.tsx` — 라우트 4개 추가

`/diagnosis/5`, `/diagnosis/6`, `/diagnosis/7`, `/diagnosis/8` → 각각 새 컴포넌트 import + Route 등록. 기존 `/diagnosis/1`~`/diagnosis/4` 등록부 바로 아래에 이어붙이면 됨.

---

### 8. 백엔드 — `backend/api/diagnosis.py` 확장 (아이디어 카드 생성 실제 연결)

`DiagnosisSubmitRequest`에 필드 추가(전부 선택값, 빈 문자열 허용):

```python
target: str = ""
differentiator: str = ""
revenue_model: str = ""
core_skill: str = ""
```

세션 INSERT(기존 로직 그대로, DB 컬럼 추가 없음 — 이 4개 값은 저장하지 않고 카드 생성에만 씀) 이후에 추가:

```python
from backend.chatbot.idea_card_generator import call_llm_for_idea_cards
from backend.chatbot.real_llm_client import call_llm

slots = {
    "target": payload.target,
    "differentiator": payload.differentiator,
    "revenue_model": payload.revenue_model,
    "core_skill": payload.core_skill,
}
try:
    card_result = call_llm_for_idea_cards(slots, llm_client=call_llm)
    cards = card_result.get("cards", [])
except Exception:
    cards = []  # 카드 생성 실패해도 세션 저장 자체는 이미 끝났으니 요청은 성공으로 처리
```

응답을 `{"success": True, "data": {"session_id": session_id, "cards": cards}}`로 변경.

**주의사항(사용자가 직접 확인 필요, 클로드 코드가 판단할 수 없는 부분)**:
- `real_llm_client.call_llm`이 `OPENAI_API_KEY` 환경변수를 읽어서 OpenAI를 실제로 호출함 — 백엔드 서버(.env)에 이 키가 설정돼 있는지 확인 필요. 없으면 `getpass`로 떨어져서 서버가 멈출 수 있음(테스트/로컬 실행 시엔 문제없지만 배포 환경에선 반드시 환경변수로).
- 이번 변경으로 `/api/diagnosis/submit` 응답이 살짝 느려짐(LLM 호출 1회 추가) — 프론트 "제출 중..." 로딩 문구는 이미 있으니 별도 처리 불필요.
- `idea_refinement_brainstorm_suggestions` 같은 카드 영구 저장용 테이블은 아직 실제 DB에 없음(설계 문서에만 있음, `db_설계_작업_컨벤션.md` 참고) — 이번엔 카드를 DB에 저장하지 않고 그 자리에서 한 번 보여주고 끝냄(제출 완료 화면 벗어나면 카드 다시 못 봄). 나중에 마이페이지 등에서 다시 보고 싶으면 그 테이블부터 DA와 확정해야 함 — 이번 범위 아님.

---

## 적용할 원칙

프로젝트 문서(`프로토타입_화면인덱스_디자인토큰_참고.md`)의 "⭐ 토큰 절약" 8개 원칙 그대로 적용(재열람 최소화, `is.xxx`/검색키 기준 검색, 기존 자산 재사용, 무거운 검증 생략, 짧은 완료 보고 등). 이번 건 추가로:
- 프론트 새 파일 4개는 전부 `DiagnosisStep2.tsx`/`DiagnosisStep3.tsx` 구조를 그대로 복사해서 슬롯 키/문구만 바꾸는 수준 — 새로운 패턴 고민할 필요 없음.
- 백엔드는 `idea_card_test.py`의 기존 호출 패턴(37~43번 줄 근처)을 그대로 참고해서 옮기면 됨 — 새로 설계하지 말 것.
