## 작업: diagnosis 화면들의 헤더/하단 버튼을 프로토타입 실제 스타일로 교체 + 선택 질문 4개 추가

**이 프롬프트가 이전에 드린 프롬프트 2개를 대체합니다**:
- "Q2·Q5 정합화" 프롬프트로 바뀐 카드 내용(문구, 옵션 개수)은 이미 정확하게 잘 반영되어 있음 — **그대로 유지, 손대지 말 것**.
- "선택 질문 4개 + 아이디어 카드 연동" 프롬프트는 아직 실행 전이면 이번 프롬프트로 대체(내용이 겹침, 헤더/하단 스펙이 이번에 새로 추가됨).

**문제**: `DiagnosisSelect.tsx`/`DiagnosisStep1~4.tsx`가 지금 쓰고 있는 헤더(뒤로가기+"사업 구체화"+"N/4" 텍스트)와 하단(버튼 1개)은 프로토타입의 실제 "isQ" 화면(진행바+단계뱃지 헤더, 상단 토픽뱃지, "이전"/"다음 →" 버튼 2개)과 다름 — 예전에 "이 프로젝트에 전용 디자인이 없어서 임시로 단순화"해둔 버전이 그대로 남아있던 것. 프로토타입 원본 그대로 맞춰야 함.

**좋은 소식**: `pages/idea/IdeaQuestions.tsx` + `styles/ideaQuestions.module.css`(이제 안 쓰는 화면)가 이 정확한 스타일을 이미 구현해뒀음 — 새로 디자인할 필요 없이 그 구조/클래스를 diagnosis 쪽으로 그대로 옮기면 됨. 필요한 토큰도 전부 이미 있음(`--color-navy-sphere`, `--color-dot-inactive`, `--shadow-inset-gray-strong`, `--shadow-inset-gray-strong-hover` 등) — **새 토큰 추가 불필요**.

[레퍼런스] 프로토타입: `C:\workspaces\10_Final\mulggo-app\docs\260910_2008_Mulkko Prototype standalone.html` — 검색 키 `qMeta` 객체 전체(재검증 불필요, 아래 표 그대로 신뢰).

---

### 1. `diagnosis.module.css` — 헤더/하단 클래스를 `ideaQuestions.module.css`에서 포팅

`ideaQuestions.module.css`의 아래 클래스를 그대로(값 동일하게) `diagnosis.module.css`에 추가/교체:
- `.header`(52px, 진행바 포함 버전으로 교체 — 기존 50px짜리 단순 헤더 대체), `.backButton`, `.progressTrack`, `.progressFill`, `.stepBadge`
- `.topicBadge` (상단 토픽뱃지, 신규 추가)
- `.bottom`, `.prevButton` (하단 2버튼 레이아웃, 신규 추가 — 기존 `.nextButton`은 재사용하되 height를 `var(--btn-height-save)` → `50px` 고정으로 통일해서 `.prevButton`과 높이 맞출 것)

기존 `.headerTitle`/`.stepLabel`(텍스트만 있던 단순 헤더용)은 이제 안 쓰면 지워도 됨. 기존 `.footer`(단일 버튼 wrapper, padding만 있음)는 제출 완료 화면("홈으로" 버튼)에서만 계속 쓰고, 질문 화면들은 전부 새 `.bottom`을 쓰도록 변경.

### 2. `DiagnosisHeader.tsx` — 진행바 헤더로 교체

props를 `{ onBack: () => void; pct: string; stepLabel: string }`로 교체(기존 `stepLabel?: string`은 제거, 이제 필수). `IdeaQuestions.tsx`의 헤더 JSX(뒤로가기 svg + `.progressTrack`/`.progressFill`(width: pct) + `.stepBadge`) 그대로 포팅.

### 3. `DiagnosisTextQuestion.tsx` — 상단 토픽뱃지 + anchor + 하단 2버튼으로 확장

새 props 추가:
```ts
topicBadge: string;       // 예: "Q1 · 사업 아이템 구상"
anchor?: string;          // 참고문구(있으면 힌트박스 렌더링)
required?: boolean;       // 기본 true. false면 글자수 미만이어도 다음 버튼 비활성화 안 함
onBack: () => void;       // 이전 버튼
backLabel?: string;       // 기본 "이전"
```
렌더링 순서: `topicBadge` → `title` → `sub` → (있으면) `anchor` 힌트박스 → `textarea` → 하단(`이전`+`다음/buttonLabel`, `.bottom`/`.prevButton`/`.nextButton` 클래스, `justify-content: space-between`로 좌우 배치).

anchor 힌트박스 스타일(프로토타입 `qAnchor` 실측값, `diagnosis.module.css`에 새 클래스로 추가):
- 박스: `background: rgba(21,50,140,.05); border-radius:12px; padding:12px 14px; box-shadow: inset 0 0 0 1.2px rgba(21,50,140,.25); display:flex; gap:8px; align-items:flex-start;`
- 아이콘(15x15, stroke `#15328C` width2, 반짝임 모양): `<path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"/>`
- 텍스트: 12.5px, `#15328C`(→ `--color-deep-navy`, 이미 있는 토큰), line-height1.55, font-weight600

### 4. `DiagnosisSelect.tsx`(Q2/07) — 헤더 추가 + 선택 후 "다음"으로 진행

- 카드 클릭 시 바로 `navigate`하지 말고, 로컬 `selected: Origin | null` state로 선택만 표시(`radioDotOn` 토글).
- 헤더: `<DiagnosisHeader onBack={handleBack} pct="40%" stepLabel="AI 제안 · 2/6" />`
- 카드 리스트 위에 `<span className={styles.topicBadge}>Q2 · 출발점</span>` 추가.
- 하단에 `.bottom`(이전/다음) 추가 — "다음"은 `selected`가 있을 때만 활성화, 클릭 시 `choose(selected)`(기존 로직 그대로 저장+`/diagnosis/1`).

### 5. `DiagnosisStep1.tsx`/`DiagnosisStep2.tsx`/`DiagnosisStep3.tsx` — 헤더/뱃지 값만 채우기

`DiagnosisTextQuestion`에 아래 표 값 그대로 전달(로직 변경 없음, props만 추가):

| 화면 | pct | stepLabel | topicBadge |
|---|---|---|---|
| DiagnosisStep1 (seedInterest) | 25% | AI 제안 · 1/6 | Q1 · 사업 아이템 구상 |
| DiagnosisStep2 (problemToSolve) | 60% | AI 제안 · 3/6 | Q3 · 문제 정의 |
| DiagnosisStep3 (solutionApproach) | 67% | AI 제안 · 4/6 | Q4 · 해결 방식 |

(Step2/3의 title은 이미 origin별로 갈리는 `DIAGNOSIS_QUESTIONS` 사용 중 — 그대로 유지, topicBadge만 고정값으로 추가)

### 6. `DiagnosisStep4.tsx`(Q5+Q6 병합 화면) — 헤더/뱃지 추가 + 제출을 뒤로 미룸

- 헤더: `pct="100%" stepLabel="AI 제안 · 6/6"` (이 화면이 필수질문 구간의 마지막이라 6/6으로 마무리).
- 매장형태 질문 블록 바로 위에 `<span className={styles.topicBadge}>Q5 · 매장 운영 형태</span>`, 지역 질문 블록 바로 위에 `<span className={styles.topicBadge}>Q6 · 지역·규모</span>` 각각 추가.
- **제출 로직을 여기서 실행하지 말고 뒤로 미룸**(아래 8번 `DiagnosisStep8`로 이동): `handleSubmit`의 fetch/제출 state/"제출 완료" 화면 JSX를 전부 삭제하고, 버튼 라벨 "제출하기"→"다음", 클릭 시 `saveDiagnosisAnswers({ storeType, sido, sigungu, dong })` 저장 후 `navigate("/diagnosis/5")`. 하단은 `.bottom`(이전+다음)으로 교체.

### 7. `diagnosisAnswers.ts` — 필드 추가

```ts
target?: string;
differentiator?: string;
revenueModel?: string;
coreSkill?: string;
```

### 8. 새 화면 4개 — `DiagnosisStep5~8.tsx`(`/diagnosis/5`~`/diagnosis/8`)

`DiagnosisStep2.tsx` 패턴(가드+`DiagnosisTextQuestion`) 그대로 복사, 슬롯 키/문구만 교체. 가드는 전부 `!answers.sido || !answers.sigungu || !answers.dong`이면 `/diagnosis/4`로 리다이렉트(선택 질문끼리는 서로 비어있을 수 있어 서로를 가드 조건으로 못 씀). `required={false}`로 호출(선택 질문이라 빈 값 허용 — `idea_card_generator.py`가 부실한 슬롯은 알아서 스킵).

| 파일 | 라우트 | slot 키 | pct | stepLabel | topicBadge | anchor | title | sub | placeholder |
|---|---|---|---|---|---|---|---|---|---|
| DiagnosisStep5 | /diagnosis/5 | target | 25% | 선택 질문 · 1/4 | Q7 · 타깃 | 유사 벤처인증기업 27개 중 연구개발형이 44%로 가장 많아요. | 이 문제를 가장 크게 겪는 고객층은 누구인가요? | 타깃을 구체적으로 정의할수록 이후 분석·매칭의 정확도가 높아집니다 | 예: 동네 직장인, 재택근무자 |
| DiagnosisStep6 | /diagnosis/6 | differentiator | 50% | 선택 질문 · 2/4 | Q8 · 차별점 | 관련 분야 특허출원이 2021년부터 꾸준히 늘고 있어요. | 기존 대안과 비교해 이 사업만의 차별점은 뭐인가요? | 경쟁 서비스·매장과 비교해 다른 점을 적어주세요 | 예: 프랜차이즈 대비 좌석 여유, 조용함 |
| DiagnosisStep7 | /diagnosis/7 | revenueModel | 75% | 선택 질문 · 3/4 | Q9 · 수익모델 | 참고한 우수사례 5건 중 3건이 좌석 이용료+상품 판매 병행 방식을 썼어요. | 어떤 방식으로 수익을 만드실 건가요? | 주요 매출원과 보조 매출원을 구분해 작성해주시면 좋습니다 | 예: 음료 판매, 공간 대여(모임룸) |
| DiagnosisStep8 | /diagnosis/8 | coreSkill | 92% | 선택 질문 · 4/4 | Q10 · 보유역량 | (없음) | 이 문제를 해결할 수 있는 본인만의 강점·경험이 있으신가요? | 자격증, 경력, 네트워크 등 구체적으로 작성해주세요 | 예: 바리스타 자격증, 요식업 경력 |

Step5→6→7→8 순서로 이전/다음 연결(값이 비어있어도 진행 허용). **Step8만 다르게 동작** — 아래 9번 참고.

### 9. `DiagnosisStep8.tsx` — 실제 제출 + 카드 결과 표시

`DiagnosisStep4.tsx`에서 삭제한 제출 로직(fetch, `submitting`/`error`/`submitted` state, "제출 완료" 화면)을 여기로 이식. `coreSkill` 답변 입력 후 "제출하기" 클릭 시, `diagnosisAnswers`에 쌓인 전체 값(origin, seedInterest, problemToSolve, solutionApproach, storeType→hasStore 파생값, sido/sigungu/dong, target, differentiator, revenueModel, coreSkill)을 모아 아래 11번 확장 payload로 `POST ${API_BASE_URL}/api/diagnosis/submit` 전송.

성공 시 응답의 `data.cards`를 받아 "제출 완료" 화면(기존 문구 "사업 구체화가 끝났어요!" 그대로)에 카드 리스트 추가:
```tsx
{cards.map((c, i) => (
  <div key={i} className={styles.resultCard}>
    <span className={styles.resultAxis}>{c.axis}</span>
    <span className={styles.resultTitle}>{c.title}</span>
    <span className={styles.resultDesc}>{c.description}</span>
  </div>
))}
```
(`.resultCard`/`.resultAxis`/`.resultTitle`/`.resultDesc`는 diagnosis.module.css에 이미 있음, 새로 안 만들어도 됨). 카드 0개면 정상(부실 답변 시 스킵) — 기존 안내문구만 보여주면 됨. `DiagnosisSubmitResponse`에 `data?.cards?: {axis,title,description}[]` 추가. 401/에러 처리는 옮겨온 로직 그대로.

### 10. `App.tsx` — 라우트 4개 추가, `/idea/questions` 제거

- `/diagnosis/5`~`/diagnosis/8` 라우트 추가(새 컴포넌트 import).
- **`IdeaQuestions` import + `<Route path="/idea/questions" .../>` 삭제** — 이 화면의 디자인이 diagnosis 쪽으로 완전히 흡수됐으므로 이제 완전 중복. `pages/idea/IdeaQuestions.tsx` + `styles/ideaQuestions.module.css` 파일도 삭제.

### 11. 백엔드 — `backend/api/diagnosis.py` (아이디어 카드 생성 연결)

`idea_card_generator.py`/`real_llm_client.py`는 **수정하지 말 것**(완성된 로직 그대로 호출만). 업종코드(KSIC) 매칭(`decide_industry`)은 다른 세션이 별도 진행 중이므로 **연결하지 말 것**.

`DiagnosisSubmitRequest`에 필드 추가(전부 선택, 빈 문자열 허용):
```python
target: str = ""
differentiator: str = ""
revenue_model: str = ""
core_skill: str = ""
```

세션 INSERT(기존 그대로, DB 컬럼 추가 없음 — 이 4개는 저장 안 하고 카드 생성에만 씀) 이후:
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
    cards = []  # 카드 생성 실패해도 세션 저장은 이미 끝났으니 요청 자체는 성공 처리
```
응답을 `{"success": True, "data": {"session_id": session_id, "cards": cards}}`로 변경.

**확인 필요(사용자 몫)**: 백엔드 서버에 `OPENAI_API_KEY` 환경변수 설정 여부(없으면 `real_llm_client.get_client()`가 `getpass`로 떨어짐).

---

## 적용할 원칙

프로젝트 문서의 "⭐ 토큰 절약" 8개 원칙 그대로 적용. 추가로:
- 이번 작업에 필요한 색상/그림자/radius 토큰은 전부 이미 있음(`IdeaQuestions.tsx`/`ideaQuestions.module.css`에서 이미 검증됨) — webTokens.css 새로 뒤질 필요 없음.
- `DiagnosisStep1~3.tsx`/새 `DiagnosisStep5~8.tsx`는 전부 같은 패턴(가드+`DiagnosisTextQuestion` 호출) — 파일마다 새로 고민하지 말고 그대로 복사해서 표의 값만 바꿀 것.
- 완료 후 무거운 검증(`npm run build` 등) 생략, 완료 보고는 3줄 이내.
