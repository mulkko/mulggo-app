## 작업: Q2(출발점)/Q5(매장 운영 형태) 화면을 프로토타입 실측값에 맞게 정합화

**중요 배경**: 이 화면들은 새로 만드는 게 아니라 이미 `pages/diagnosis/` 아래 구현되어 있음. 이번 작업은 (1) `IdeaChoice.tsx`의 라우팅을 문서와 일치시키고, (2) `DiagnosisSelect.tsx`(Q2)와 `DiagnosisStep4.tsx`(Q5) 두 화면의 **문구/옵션 구성**을 프로토타입 실측값으로 교체하는 것. 새 파일 만들 필요 없음.

[레퍼런스] 프로토타입 파일: `C:\workspaces\10_Final\mulggo-app\docs\260910_2008_Mulkko Prototype standalone.html` — 검색 키: `qMeta` 객체의 `q1`(Q2, kind:'pick'), `q3b`(Q5, kind:'store') 항목과 `renderVals()`의 `qKind.pick`/`qKind.store` 렌더 분기. (아래 실측값을 이미 정확히 뽑아뒀으니 재검증 목적으로 다시 열어보지 말 것 — 값이 애매하거나 빠진 부분이 있을 때만 열어볼 것.)

---

### 1. `frontend/src/pages/idea/IdeaChoice.tsx` — 라우팅 정합

- `startFast`, `startPrecise` 두 핸들러 안의 `navigate("/idea/questions")`를 **`navigate("/diagnosis/select")`로 변경**. (컴포넌트 상단 docblock 주석엔 이미 "두 카드 모두 `/diagnosis/select`로 이어진다"고 적혀 있는데 실제 코드가 `/idea/questions`로 가고 있던 불일치를 바로잡는 것.)
- "빠른 매칭"/"정밀 구체화" 트랙별 질문 수 분기는 이번 범위 아님, TODO 주석 그대로 둠.

### 2. `frontend/src/pages/diagnosis/DiagnosisSelect.tsx` — Q2(07) 문구·스타일 교체

현재 카드 문구(부연 설명 붙어 있음)를 아래 프로토타입 실측값으로 정확히 교체:

- 카드1: 제목 `① "불편했던 경험에서"`, 설명 `문제 해결형`
- 카드2: 제목 `② "이런 게 있으면 좋겠다"`, 설명 `기회 추구형`

질문 타이틀/서브는 이미 프로토타입과 동일하니 그대로 둠 (`이 아이디어는 어디서 출발했나요?` / `두 갈래 중 가까운 쪽을 골라주세요`).

클릭 시 바로 다음 화면(`/diagnosis/1`)으로 넘어가는 현재 동작(별도 "다음" 버튼 없음)은 그대로 유지 — 문제없이 동작 중이라 안 바꿈.

카드 시각 스펙을 아래 3번에서 만드는 라디오카드 스타일로 교체(현재 `.choiceCard`는 onboarding 카드 스펙을 임시로 재사용 중이던 것):

- radius14, padding17, gap5
- `box-shadow: inset 0 0 0 1.5px rgba(139,141,147,.3)`, hover `inset 0 0 0 1.5px #3FB6A8`
- 우측 라디오 원(18x18, border 1.5px `rgba(139,141,147,.3)`), hover/선택 시 안쪽에 10x10 `#15328C` 원 표시 — 참고: 이 화면은 클릭 즉시 다음으로 넘어가므로 "선택된 상태"가 화면에 오래 머물진 않지만, 클릭 순간 시각 피드백용으로 라디오 dot on 상태를 잠깐이라도 넣을 수 있으면 넣고, 구현이 번거로우면 생략해도 됨(우선순위 낮음)
- 제목 700/14.5px `#2E312E`, 설명 12px `#8B8D93`(→ `--color-stone-gray`)

### 3. `frontend/src/styles/diagnosis.module.css` — 공용 라디오카드 스타일 추가

위 스펙으로 새 클래스 추가(이름 자유, 예: `.radioCard`, `.radioCardHead`, `.radioDot`, `.radioDotOn`, `.radioCardTitle`, `.radioCardDesc`). 아래 5번(Q5)에서도 그대로 재사용할 것이므로 padding/gap/폰트크기는 인라인 스타일이나 modifier 클래스로 오버라이드 가능하게 만들어둘 것(Q2는 padding17/gap5/제목14.5px, Q5는 padding15/gap4/제목14px로 서로 다름).

색상값(`#3FB6A8`, `#15328C`, `rgba(139,141,147,.3)`)은 `webTokens.css`에 이미 대응 토큰이 있는지 먼저 확인: `nextButton`이 이미 `--color-light-teal`을 배경으로 쓰고 있고 프로토타입의 "다음" 버튼 배경도 `#3FB6A8`이라 같은 값일 가능성이 높음 — 대조해서 확인 후 있으면 그 토큰 사용, 없는 값만 새로 추가.

기존 `.choiceCard`/`.choiceCardSelected`(onboarding 스펙 재사용이던 것)는 다른 파일에서 더 안 쓰면 지워도 되고, 남아있는 곳 있으면 grep해서 확인 후 판단.

### 4. `frontend/src/pages/diagnosis/diagnosisAnswers.ts` — 타입 확장

`DiagnosisAnswers` 인터페이스에 필드 추가:

```ts
storeType?: StoreType;
```

새 타입 추가:

```ts
export type StoreType = "offline" | "booking" | "delivery" | "online" | "digital";
```

(매핑 참고용 — 5번에서 그대로 사용: `offline`=①고객방문형 오프라인 매장·공간, `booking`=②예약 방문형 서비스 공간, `delivery`=③배달·제조 중심 고객방문없음, `online`=④온라인 판매·중개 플랫폼, `digital`=⑤앱·소프트웨어·디지털 서비스)

기존 `hasStore?: boolean` 필드는 그대로 남겨둬도 되고 지워도 됨(6번 참고 — 파생값으로만 쓰이므로 굳이 저장 안 해도 무방, 편한 쪽으로).

### 5. `frontend/src/pages/diagnosis/DiagnosisStep4.tsx` — Q5(09-1)를 프로토타입 5지선다로 교체

현재 "예/아니오" 2지선다(`hasStore: boolean | null`, `.choiceCard` 2개)를 아래 프로토타입 실측값 그대로 5개 라디오 카드로 교체:

| value | 제목 | 설명(ex.) |
|---|---|---|
| offline | ① 고객 방문형 오프라인 매장·공간 | ex. 카페, 미용실, 학원 |
| booking | ② 예약 방문형 서비스 공간 | ex. 공유스튜디오, 상담실 |
| delivery | ③ 배달·제조 중심, 고객 방문 없음 | ex. 공장, 배달전문 주방 |
| online | ④ 온라인 판매·중개 플랫폼 | ex. 쇼핑몰, 중고거래앱 |
| digital | ⑤ 앱·소프트웨어·디지털 서비스 | ex. 구독 SaaS |

- 카드 스펙: 3번에서 만든 라디오카드 재사용하되 radius14, padding15, gap4, 제목 700/14px, 설명 11.5px (Q2보다 살짝 촘촘함).
- state를 `hasStore: boolean | null` → `storeType: StoreType | null`로 변경. 선택된 카드는 라디오 dot on 상태로 표시(기존 `choiceCardSelected` 방식과 동일한 아이디어, 클래스명만 새 스타일에 맞게).
- 질문 타이틀/서브를 프로토타입 그대로 교체: 제목 `사업을 어떤 형태로 하시나요?`, 서브 `오프라인 매장 여부에 따라 분석 리포트 구성이 달라져요`. (기존 "고객이 직접 방문하는 매장이나 공간을 운영하시나요?"는 2지선다 시절 문구라 교체)
- `canSubmit` 조건의 `hasStore !== null` → `storeType !== null`로 변경.
- `handleSubmit`에서 기존 백엔드 payload는 그대로 `has_store: boolean`을 받으므로(백엔드/DB 스키마 변경은 이번 범위 아님) `storeType`에서 파생해서 보낼 것:

```ts
const hasStoreDerived = storeType === "offline" || storeType === "booking";
```

`saveDiagnosisAnswers({ storeType, sido, sigungu, dong })`으로 저장하고(hasStore는 굳이 별도 저장 안 해도 됨), 제출 payload의 `has_store` 필드에는 `hasStoreDerived` 값을 넣을 것.

---

## 토큰 절약 (항상 지킬 것)

1. 위 실측값은 이미 프로토타입에서 정확히 뽑은 값이니 다시 열어서 재검증하지 말 것. 단, 레퍼런스 경로/검색 키는 그대로 유지하고 있을 것.
2. 화면 라벨 텍스트 대신 `is.xxx`/상태 키로 검색하는 습관 유지(이번 건 로컬 코드 직접 수정이라 해당 없음).
3. 기존 컴포넌트/클래스/토큰 최대한 재사용, 프로젝트 전체 탐색 금지 — 위에 지정한 파일만 건드릴 것.
4. `webTokens.css`에 이미 있다고 확인되는 토큰은 재검색 없이 바로 사용.
5. 작업 후 `npm run build`, 전체 타입체크, dev 서버 재시작 등 무거운 검증 생략.
6. 완료 보고는 3줄 이내로, 작성한 코드를 다시 붙여넣지 말 것.
7. 로고 관련 변경 없음 — 이번 작업 범위 아님.
