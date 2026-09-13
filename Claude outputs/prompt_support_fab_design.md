[작업 배경]
"1:1 문의" 화면(`pages/support/CustomerSupport.tsx`, 라우트 `/support`)에 아래 3가지를 적용한다. **기능/상태/유효성검사/제출 로직/백엔드는 절대 손대지 않는다 — 색상·스타일·아이콘 교체만.**

1. 우측 하단 플로팅 챗봇 버튼(FAB) 추가 — 이번엔 이 화면 하나에만 넣는 시험 적용이다. 나중에 다른 화면에도 넣기로 결정되면 그때 공용 컴포넌트로 뽑아서 여러 화면에 재사용할 수 있게(예: 레이아웃 레벨 컴포넌트로) 다시 정리할 수 있으니, 지금은 `pages/support/CustomerSupport.tsx` 안에서만 렌더링하면 됨 — 다른 화면 건드릴 필요 없음.
2. "챗봇에게 먼저 물어보기" 카드 색/테두리를 프로토타입과 동일하게, 아바타 아이콘을 이미지로 교체
3. "건의사항" textarea / "답변 받을 이메일" input 색을 프로토타입과 동일하게

[레퍼런스]
프로토타입 파일: `docs/260912_2011_Mulkko Prototype (standalone).html`(최신본). grep 키: `is.cs`(19번 문의하기 화면, 파일에 2번 나오는데 **두 번째가 실제 화면**). FAB는 이 화면 전용 마크업이 아니라 프로토타입 전역 로직(`showFab`/`fabTop`/`fabBottom`)으로 대부분 화면에 공통으로 뜨는 요소인데, 이번엔 그 전역 로직까지 옮길 필요 없이 아래 [실측 디자인 값]의 스타일만 이 화면에 로컬로 적용하면 됨.
아이콘 에셋: `frontend/src/assets/8_white.svg`(또는 `.png`, 둘 중 로드 잘 되는 걸로) — FAB 마스코트. `frontend/src/assets/9_mint.svg`(또는 `.png`) — 챗봇 카드 아바타.
"프로토타입 검토 원칙" 등 토큰 절약 원칙 항상 적용, 아래 값으로 충분하면 파일 다시 열어볼 필요 없음.

[실측 디자인 값]

**1) FAB (플로팅 챗봇 버튼)** — 56x56 원형, `overflow:hidden`, 내부에 `8_white` 이미지를 `width:100%; height:100%; object-fit:cover`로 꽉 채움(별도 배경색 없이 이미지 자체가 원을 채우는 형태). `box-shadow: 0 10px 24px -6px rgba(21,50,140,.45), 0 4px 10px -2px rgba(21,50,140,.3)`, 클릭 시 `/support/chat`으로 이동(기존 `handleChatCardClick`과 동일 목적지, 즉 같은 핸들러 재사용해도 됨). 위치: 화면 우측 하단 고정 — `right:16px`, 이 페이지엔 하단 탭바가 없으니 `bottom:20~24px` 정도(정확한 값은 페이지 여백 보고 자연스럽게). `.page` 컨테이너가 모바일 640px 폭으로 가운데 정렬돼 있으니, 버튼도 그 컨테이너 기준 우측하단에 고정되도록(뷰포트 전체 기준으로 붙어서 데스크톱에서 어색하게 떨어져 보이지 않게) — 컨테이너에 `position:relative` 필요하면 추가해도 됨. `z-index`는 페이지 내 다른 요소보다 충분히 높게.

**2) "챗봇에게 먼저 물어보기" 카드** (`.chatCard` 등, 지금 코드는 흰 배경+옅은 그림자+34x34 SVG 아이콘) → 아래로 교체:
- 배경 `#DFF3EF`, `border-radius:14px`, `padding:16px`, `box-shadow: inset 0 0 0 1.2px rgba(63,182,168,.4)`, hover `inset 0 0 0 1.2px rgba(63,182,168,.7)`
- 아바타: 52x52 원형, 배경 `#3FB6A8`, `overflow:hidden` — 안의 SVG 아이콘(`BotAvatarIcon`) 대신 **`9_mint` 이미지를 `width:100%; height:100%; object-fit:cover`로 채워서 동그랗게 잘려 보이게**(`CustomerSupportChat.tsx`의 `BotAvatarIcon` export 자체는 다른 데서도 쓰일 수 있으니 그건 그대로 두고, 이 파일 안에서만 이미지로 바꿔서 렌더)
- 제목 "챗봇에게 먼저 물어보기": `font-weight:700; font-size:14px; color:#0F6E62`(현재 `--color-ink-charcoal`에서 이 색으로 변경)
- 부제 "자주 묻는 질문은 챗봇이 바로 답해드려요": `11.5px; color:#8B8D93`(기존과 거의 동일, 유지)
- 화살표 아이콘: 16x16, `stroke:#0F6E62`

**3) 입력 필드**
- 건의사항 textarea: `border:1.5px solid rgba(63,182,168,.35)`, 배경 `#DFF3EF`, `border-radius:13px`, `padding:13px 15px`, `font-size:13px`, `line-height:1.6`(높이는 지금 `min-height:120px` 유지해도 됨, 프로토타입은 110px로 큰 차이 없음)
- 답변 받을 이메일 input: `border:1.5px solid rgba(63,182,168,.35)`, 배경 `#FFFFFF`, `border-radius:12px`, `height:48px`, `padding:0 15px`, `font-size:13px`
- 포커스/에러 상태 스타일(`.input:focus`, `.inputError` 등)은 기존 로직 그대로 유지, 색상 토큰만 위 값으로 바꾸면 됨. placeholder, 유효성 검사 문구, 제출 버튼 동작은 전혀 안 건드림.

[작업 다 되면 알려줘]
FAB 추가됐는지, 챗봇 카드/인풋 색이 바뀌었는지, 기존 유효성검사·제출 로직은 그대로인지만 3줄 이내로 알려줘.
