[작업 배경]
FAB 롤아웃 목록에서 하나 빠뜨렸다 — `DiagnosisReportSummary.tsx`(13-1/14-2 "리포트 파트2", `DiagnosisStep9.tsx` 제출 완료 시 실제로 렌더링되는 컴포넌트이자 `DiagnosisReportSummaryPreview.tsx`가 미리보는 대상)도 프로토타입 `showFab` 규칙상 포함 대상. 앞선 롤아웃 프롬프트로 만든 `components/ChatFab/ChatFab.tsx`가 이미 있다는 전제(없으면 그 프롬프트 먼저 적용).

[수정 내용]
`DiagnosisReportSummary.tsx`에 `<ChatFab variant="top" />` 추가. 이 화면도 하단에 "이전"/"지원사업 매칭 보기 →" 버튼(`.footer`)이 고정돼 있어서, `DiagnosisIndustryCode.tsx`와 동일하게 `top` variant(우측상단, `top:60px`)로 배치해서 겹치지 않게. 페이지 최상위 컨테이너 안에 형제 레벨로 한 줄만 추가, 다른 레이아웃/로직은 건드리지 않음.

[작업 다 되면 알려줘]
추가됐는지, 하단 버튼이랑 안 겹치는지만 1~2줄로 알려줘.
