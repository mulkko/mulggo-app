[작업 배경]
`/support`(CustomerSupport.tsx)에 넣은 플로팅 챗봇 버튼(FAB) 디자인이 확정됐으니, 이번엔 이걸 공용 컴포넌트로 뽑아서 프로토타입의 `showFab` 규칙에 해당하는 다른 화면에도 추가한다. 이 코드베이스는 하단탭바(`BottomNav`)도 전역 자동삽입이 아니라 필요한 화면마다 직접 `<BottomNav />`를 넣는 방식이니, FAB도 같은 패턴(화면마다 필요한 곳에 직접 배치)으로 간다 — 화면끼리 서로 영향 안 주고 안전함.

[1) 공용 컴포넌트로 추출]
`components/ChatFab/ChatFab.tsx` + `ChatFab.module.css` 새로 생성(폴더 구조는 `components/BottomNav/BottomNav.tsx`와 동일한 컨벤션). `CustomerSupport.tsx`에 지금 완성된 FAB 마크업/스타일(`8_white.png` import, `.fab`/`.fabImg`)을 그대로 이 컴포넌트로 옮기고, `CustomerSupport.tsx`에서는 `<ChatFab />`으로 교체 — **시각적으로 지금과 완전히 동일해야 함**, 스타일 재작성 금지.

컴포넌트는 위치 변형 3가지를 props로 받게 만들 것(`variant?: "default" | "withBottomNav" | "top"`, 기본값 `"default"`):
- `default`: 지금 `/support`에 쓰는 값 그대로 (`right:16px; bottom:24px`)
- `withBottomNav`: 하단탭바(BottomNav, 높이74px)가 있는 화면용 — `right:16px; bottom:90px`(탭바에 안 가리게)
- `top`: `right:16px; top:60px; bottom:auto`(하단에 다른 CTA 버튼이 있는 화면용)

클릭 시 `/support/chat`으로 이동하는 로직은 그대로 유지.

[2) 아래 화면에 `<ChatFab />` 추가]

| 파일 | variant |
|---|---|
| `pages/home/Home.tsx` | `withBottomNav` |
| `pages/mypage/MyPage.tsx` | `withBottomNav` |
| `pages/matching/MatchingList.tsx` | `withBottomNav` |
| `pages/matching/MatchingDetail.tsx` | 이 화면에 `<BottomNav />`가 실제로 렌더링되고 있으면 `withBottomNav`, 없으면 `default` — 파일 열어서 확인하고 맞는 쪽으로 |
| `pages/diagnosis/DiagnosisChoice.tsx` | `default` |
| `pages/diagnosis/DiagnosisIndustryCode.tsx` | `top` (이 화면은 하단에 "이전"/"분석 리포트 보러가기" 버튼이 이미 있어서 겹치지 않게 위쪽 배치) |
| `pages/diagnosis/DiagnosisMarketReport.tsx` | `default` |
| `pages/diagnosis/DiagnosisTechReport.tsx` | `default` |

각 파일에서 페이지 최상위 컨테이너(`pageContainer` 등) 안, 다른 콘텐츠와 형제 레벨로 `<ChatFab variant="..." />` 한 줄만 추가하면 됨 — 레이아웃 구조를 바꾸지 말 것.

[3) 절대 추가하지 말 것 — 아래 화면은 프로토타입 규칙상 FAB 제외 대상]
`Splash.tsx`, `LoginForm.tsx`, `Signup.tsx`, `Onboarding.tsx`, 진단 질문 화면 전체(`DiagnosisSelect`, `DiagnosisStep1`~`DiagnosisStep9`), `DiagnosisPsstConfirm.tsx`, `FilterPage.tsx`, `DocPreview.tsx`, `ProfileEdit.tsx`, `ProfileEditV2.tsx`, `CustomerSupportChat.tsx`(이미 챗봇 화면 안에 있으니 자기 자신에겐 불필요).

[4) 확인할 것 — 기능/레이아웃 충돌]
- `App.tsx`의 `DevAuthBadge`(임시 디버그용, 우하단 고정, z-index:9999)와 위치가 겹칠 수 있는데, 크기가 훨씬 작고(14px 점) 임시 삭제 예정인 요소라 무시해도 됨 — 다만 클릭 영역이 겹쳐서 서로 클릭을 가로채면 안 되니, 겹쳐 보이면 `DevAuthBadge`는 안 건드리고 `ChatFab`의 `right` 값만 살짝(예: 20px) 조정해도 됨.
- 각 화면에 추가한 뒤 로컬 개발서버에서 한 번씩 눈으로 확인 — 특히 `withBottomNav` 적용한 화면에서 탭바랑 안 겹치는지, `top` 적용한 `DiagnosisIndustryCode.tsx`에서 헤더나 카드 리스트 스크롤이랑 안 겹치는지.
- 기존 화면들의 클릭/네비게이션 로직은 전혀 건드리지 말 것 — FAB 추가만.

[작업 다 되면 알려줘]
공용 컴포넌트 분리됐는지, 8개 화면에 다 추가됐는지, `MatchingDetail.tsx`는 어느 variant로 갔는지, 겹침 문제 있었는지만 4줄 이내로 알려줘.
