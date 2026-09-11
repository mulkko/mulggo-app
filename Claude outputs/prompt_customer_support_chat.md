## 작업: 고객센터 챗봇 화면(19-1) 디자인을 프로토타입 실측값으로 업그레이드

**배경 확인 결과**: 이미 다 있음 — `frontend/src/pages/support/CustomerSupport.tsx`(라우트 `/support`)가 백엔드 `POST /api/support/chat`(`backend/api/support.py` → `backend/customer_chatbot/customer_service_bot.py`)에 **이미 정상적으로 연결되어 동작 중**. 다른 분이 "디자인 시안 없이 기능 확인용으로 최소 형태"로 만들어둔 상태(본인 주석에 명시)라, 이번 작업은 **디자인만 프로토타입 수준으로 끌어올리는 것** — 백엔드 연동 로직(`fetch`, request/response 형태)은 이미 맞게 되어 있으니 **하나도 건드리지 말 것**.

**추천 방식(질문하신 "백엔드 같이 연결 vs 나중에" 답)**: 이미 연결되어 있어서 고민할 필요가 없음 — 이번 라운드는 순수 프론트 디자인 작업.

**라우트**: 그대로 `/support` 유지(바꿀 이유 없음).

[레퍼런스] 프로토타입: `C:\workspaces\10_Final\mulggo-app\docs\260910_2008_Mulkko Prototype standalone.html` — 검색 키 `is.csChat`(화면), `csTopics`/`kb`(FAQ 9개+지식문서, 참고만 — 실제 지식문서는 이미 `backend/customer_chatbot/고객센터_챗봇_지식문서_v1.md`로 따로 있으니 재확인 불필요), `renderVals()`의 `csMessages`/`csChips` 계산부(재검증 불필요, 아래 값 그대로 신뢰).

---

### 1. 제목 변경

헤더 타이틀 "고객센터" → **"챗봇 상담"**으로 변경(사용자 명시 요청 — 프로토타입 원문은 "고객센터 챗봇"이지만 이걸로 바꾸는 것). 초기 인사말(`INITIAL_MESSAGE.text`)도 "고객센터" 대신 이 이름에 맞게 자연스럽게 다듬을 것: `"안녕하세요! 물꼬 챗봇 상담이에요. 아래 주제를 눌러보거나 궁금한 점을 자유롭게 물어보세요."`

### 2. 헤더에 봇 아바타 추가

현재 헤더는 뒤로가기+제목만 있음. 프로토타입은 제목 앞에 34x34 원형 아바타(배경 `#3FB6A8`→`--color-light-teal`)가 있음 — 프로토타입은 이미지 에셋을 쓰지만 우리 코드베이스엔 그 에셋이 없으니, **로고가 아닌 범용 챗봇 아이콘 SVG**(흰색 stroke)를 원 안에 넣을 것(브랜드 로고 `logo.svg`를 여기 쓰지 말 것 — 챗봇 아바타는 로고가 아님). 아이콘 예시(말풍선 모양, 그대로 써도 됨):
```
<svg viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" /></svg>
```
같은 아이콘을 봇 메시지 버블 옆(30x30, 아래 3번) + 로딩 버블 옆(30x30, 아래 5번)에도 재사용.

### 3. 봇 메시지에 아바타 붙이기

현재 봇 버블은 아바타 없이 버블만 있음. 봇 메시지 행에 왼쪽에 30x30 원형 아바타(2번과 동일 아이콘) 추가. 버블 색상은 이미 정확함(`.botBubble` bg `--color-stone-mist` / color `--color-ink-charcoal`, `.userBubble` bg `--color-light-teal` / color 흰색 — 프로토타입 실측값 `bg:'#F1F1F3'/color:'#2E312E'`(봇), `bg:'#3FB6A8'/color:'#FFFFFF'`(유저)와 이미 일치함, **바꾸지 말 것**).

### 4. FAQ 주제 칩 추가 (현재 전혀 없음 — 새 기능)

메시지 영역 아래, 입력창 위에 가로 스크롤 칩 목록 추가. 클릭하면 그 칩의 고정 질문을 **입력창에 채우지 말고 바로 전송**(아래 8번 `sendMessage` 헬퍼로 처리).

칩 라벨(그대로 9개, 클릭 시 전송할 질문은 괄호 안 텍스트):
1. 사업 아이디어 입력 (사업 아이디어는 몇 가지 질문에 답하면 되나요?)
2. 업종코드 확인 (업종코드는 어떻게 확인되나요?)
3. 아이디어 추천 (추천 아이디어를 보면 제 원래 계획이 바뀌나요?)
4. 지원사업 매칭 (지원사업 필터에는 어떤 항목들이 있나요?)
5. 분석 리포트 (특허출원 추이는 왜 2025년까지만 나오나요?)
6. 마이페이지 (마이페이지에서는 뭘 확인할 수 있나요?)
7. 문의하기 (문의하면 챗봇이 바로 답변을 주나요?)
8. 회원가입·사업자등록증 (사업자등록증 인식이 잘 안되면 어떻게 하나요?)
9. 신청서 자동입력(채우기) (채우기 기능은 어떻게 작동하나요?)

칩 스타일(프로토타입 실측값): `flex-shrink:0; font-size:11.5px; font-weight:600; color:#2E312E(→--color-ink-charcoal); background:#FFFFFF; padding:7px 12px; border-radius:99px(→--radius-pill); box-shadow: inset 0 0 0 1.2px rgba(139,141,147,.3); white-space:nowrap; cursor:pointer;` hover는 `box-shadow: inset 0 0 0 1.2px #3FB6A8`.

### 5. "답변 작성 중..." 로딩 버블 추가

지금은 `sending` 중에 입력창만 비활성화되고 별도 시각 피드백이 없음. `sending`이 true인 동안 메시지 목록 맨 아래에 아바타+버블(`배경 #F1F1F3(→--color-stone-mist), 텍스트 #8B8D93(→--color-stone-gray)`, 텍스트 "답변 작성 중...") 하나를 추가로 렌더링(실제 메시지 배열에 넣지 않고 `sending`일 때만 조건부 렌더).

### 6. 문의 접수 안내를 pill 스타일로

`needsHumanSupport`일 때 지금은 평문 안내 텍스트만 있음. 프로토타입처럼 pill 모양으로 바꾸되(`font-size:11.5px; font-weight:700; color:--color-teal-green; background:--color-teal-mist; padding:7px 12px; border-radius:--radius-pill;`), **클릭 가능한 링크로는 만들지 말 것** — 이동할 문의 접수 화면(19번 고객센터 허브)이 아직 없음. 텍스트는 "문의 접수 화면은 준비 중이에요"처럼 현재 상태에 맞게 조정.

### 7. 입력창 — 알약(pill) 모양 + 원형 전송 버튼으로 교체

- 인풋: `border-radius: 99px(→--radius-pill)`, `border: 1.5px solid rgba(139,141,147,.3)`(기존 값이 있으면 그 토큰 재사용, 없으면 이 값 그대로), 높이 46px, 배경 흰색(현재 `--color-stone-mist` 배경으로 되어있는데 프로토타입은 흰 배경 + 테두리 방식이라 흰 배경으로 교체).
- 전송 버튼: 텍스트("전송"/"...") 대신 46x46 원형 버튼(`background: --color-light-teal`)에 종이비행기 아이콘 SVG(흰색):
```
<svg viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13" /><path d="M22 2 15 22l-4-9-9-4 20-7Z" /></svg>
```
전송 중일 때는 버튼 비활성화만 하고(기존 `disabled` 로직 유지) 아이콘은 그대로 둬도 됨.

### 8. `sendMessage(question: string)` 헬퍼로 리팩터링

현재 `handleSend`는 `input` state 값만 보냄 — 칩 클릭도 처리할 수 있게 공통 함수로 추출:
```ts
const sendMessage = async (question: string) => {
  const q = question.trim();
  if (!q || sending) return;
  setMessages((prev) => [...prev, { role: "user", text: q }]);
  setInput("");
  setError("");
  setSending(true);
  try {
    // 기존 fetch 로직 그대로
  } finally {
    setSending(false);
  }
};

const handleSend = () => sendMessage(input);
const handleChipClick = (question: string) => sendMessage(question);
```

---

## 적용할 원칙

프로젝트 문서의 "⭐ 토큰 절약" 8개 원칙 그대로 적용. 추가로:
- **백엔드는 전혀 건드리지 말 것** — 이미 완성돼 있고 정상 연결됨(`backend/api/support.py`, `backend/customer_chatbot/*`). 이번 프롬프트는 프론트 디자인 작업만.
- 색상/토큰 대부분 이미 webTokens.css에 있음(`--color-light-teal`, `--color-stone-mist`, `--color-ink-charcoal`, `--color-teal-mist`, `--color-teal-green`, `--radius-pill` 등) — 확인 후 재사용, 없는 값만 추가.
- 완료 후 무거운 검증 생략, 완료 보고 3줄 이내.
