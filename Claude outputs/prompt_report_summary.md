[작업 배경]
지금 사업구체화 진단 플로우의 마지막 단계(`DiagnosisStep9.tsx`, 라우트 `/diagnosis/10`)는 `/api/diagnosis/submit` 성공 시 `.resultCard`/`.resultAxis`/`.resultTitle`/`.resultDesc`로 아이디어 카드 3장만 임시 스타일로 보여주고 있다. 이번엔 이 "제출 완료 후 결과 화면"을 프로토타입의 13-1/14-2 "리포트 파트2" 화면 디자인으로 새로 만든다.

이 화면은 **하나의 컴포넌트를 재사용**한다 — 사용자가 진단 흐름에서 앞서 상권분석 리포트(`/diagnosis/market-report`)를 봤는지 기술창업분석 리포트(`/diagnosis/tech-report`)를 봤는지에 따라 "이전" 버튼 목적지만 달라지고 나머지 레이아웃은 완전히 동일하다(프로토타입에서도 `is.reportASum`/`is.reportBSum` 두 화면이 구조는 100% 동일, `nav.reportA`/`nav.reportB`만 다름). 새 컴포넌트 `pages/diagnosis/DiagnosisReportSummary.tsx` + `styles/diagnosisReportSummary.module.css`를 만들고 `variant: "market" | "tech"` prop으로 이전 버튼 목적지를 결정하게 해줘. 지금은 실제 흐름상 상권분석 리포트만 연결돼 있으니(기술창업 리포트는 아직 nav에서 안 연결됨) `DiagnosisStep9.tsx`에서 쓸 땐 `variant="market"`으로 고정해서 넘기면 됨 — `variant="tech"` 케이스는 나중에 기술창업 리포트가 연결될 때를 위해 prop만 미리 만들어두는 것.

`DiagnosisStep9.tsx`의 `submitted` 분기 안 지금 있는 안내 문구(`사업 구체화가 끝났어요!` 제목 + 안내 문단)와 `.resultCard` 반복 렌더는 이 새 컴포넌트로 완전히 교체한다. `IdeaCard { axis, title, description }` 타입과 제출 성공 시 받는 `cards` 배열은 그대로 새 컴포넌트에 props로 넘기면 됨(백엔드 응답 형태 자체는 안 건드림). `clearDiagnosisAnswers()`가 제출 성공 즉시 호출되는 지금 순서는 그대로 둬도 되는데, 새 화면이 렌더할 때 필요한 값(타깃/차별점/수익모델/보유역량 4개 텍스트)은 sessionStorage가 지워지기 전에 이미 React state로 들고 있어야 하니, 필요하면 제출 성공 시점에 이 4개 값도 함께 로컬 state에 저장해서 넘겨줘.

우측 하단 플로팅 챗봇 버튼(FAB)은 프로토타입 다른 화면들에 있는 걸 이번에 같이 봤을 수 있는데, **이번 라운드에서는 만들지 않아도 됨** — 이 화면에도 넣지 말 것.

[레퍼런스]
프로토타입 파일: `docs/260911_Mulkko Prototype (standalone).html`(최신본, 이전 260910이 아니라 이걸로 볼 것). grep 키: `is.reportASum`(상권분석 버전, 13-1) / `is.reportBSum`(기술창업 버전, 14-2) — 각 키가 파일에 2번씩 나오는데 **두 번째 등장이 실제 화면 블록**. 둘은 아래 [실측 디자인 값]에 있는 것처럼 구조가 완전히 동일하니, 아래 값만으로 충분하면 파일을 다시 열어볼 필요 없음(다른 값 애매한 부분 있을 때만 최소로 확인).
"프로토타입 검토 원칙" 등 토큰 절약 원칙 항상 적용.

[실측 디자인 값] (`is.reportASum`/`is.reportBSum` 공통 — 둘의 유일한 차이는 이전 버튼 목적지)

**헤더 (52px, 흰 배경, `display:flex; align-items:center; gap:10px; padding:0 22px`)**
- 뒤로가기 svg(stroke `#2E312E` 2.6, path `M16 5l-8 7 8 7`) — market variant는 `/diagnosis/market-report`로, tech variant는 `/diagnosis/tech-report`로
- "MULKKO REPORT" (Inter/900/17px/letter-spacing .01em/`#15328C`)
- 로고 이미지 28px 너비 — `frontend/src/assets/logo.svg` 재사용(다른 화면들과 동일 패턴, `import logo from '../../assets/logo.svg'`)

**서브헤더 (38px, 배경 `#3FB6A8`, `padding:0 22px`, 흰 텍스트 700/14px)**
- 원문은 "이렇게 정리했어요"인데, **이 화면에서는 문구를 "사업구체화 리포트"로 바꿔서 써줘.**

**본문 (`padding:14px 20px 20px`, column, gap12)**

1) 4축 요약 카드 — 흰배경 radius12 padding14 column gap9, `box-shadow:inset 0 0 0 1.2px #E3E3E6`. 안에 4행(각 행 `display:flex; align-items:center; gap:8px`):
   - 아이콘 원 22x22 radius50%, 흰 텍스트/기호, `font-size:11px`, 가운데정렬 — 색상: 타깃 배경`#3FB6A8` 기호"◎" / 차별점 배경`#7C5CBF` 기호"✦"(프로토타입 예시 데이터에 "◆"로도 한 번 나오는데 어느 쪽이든 통일해서 쓰면 됨) / 수익모델 배경`#15328C` 기호"$"(font-weight:700) / 보유역량 배경`#E8A93C` 기호"☉"
   - 각 행 아이콘 옆: 라벨(10px/700/`#8B8D93`, "타깃"/"차별점"/"수익모델"/"보유역량") + 값(12px/700/`#2E312E`/line-height1.4) — 값은 diagnosisAnswers의 target/differentiator/revenueModel과, 지금 이 화면 진입 직전에 입력한 coreSkill을 그대로 채움

2) 헤딩 블록(column gap4): "지금 방향도 좋아요."(900/16px/`#2E312E`) + "참고해볼 만한 아이디어를 몇 가지 추천드려요."(11.5px/`#8B8D93`/line-height1.5) + "✨ AI가 답변을 바탕으로 만든 참고 아이디어예요"(10.5px/`#A9ABB2`)

3) 아이디어 카드 3장(`cards` 배열 그대로 map, 각 `axis`가 뱃지 텍스트·톤을 결정) — 카드: radius14 padding16 column gap8. 축별 색:
   | axis 값(예상) | 카드 배경 | 카드 shadow(inset) | 뱃지 배경 | 뱃지 텍스트색 |
   |---|---|---|---|---|
   | 타깃 관점 | `rgba(63,182,168,.06)` | `1.2px rgba(63,182,168,.35)` | `#BFEAE1` | `#0B5A50` |
   | 수익모델 관점 | `rgba(21,50,140,.05)` | `1.2px rgba(21,50,140,.3)` | `#C9D6F6` | `#102569` |
   | 보유역량 활용 | `rgba(232,169,60,.08)` | `1.2px rgba(232,169,60,.45)` | `#F3DA9B` | `#714800` |

   (백엔드가 실제로 내려주는 `axis` 문자열이 이 3개 중 하나와 정확히 일치하는지는 `idea_card_generator.py` 쪽 확인해서 매칭 — 혹시 다른 축이 더 있거나 문구가 살짝 다르면 가장 가까운 색 조합을 쓰거나 fallback 톤 하나 추가해도 됨)
   - 뱃지: `font-size:11px; font-weight:800; padding:5px 11px; border-radius:99px; align-self:flex-start` — 텍스트는 `axis` 값 그대로
   - 제목(`title`): `font-weight:800; font-size:15px; color:#2E312E`
   - 설명(`description`): `font-size:12.5px; color:#8B8D93; line-height:1.6`

4) 캡션: "참고용 아이디어예요 · 원래 계획은 그대로 유지해요" (11.5px/`#8B8D93`/line-height1.6)

5) 하단 버튼 2개(`display:flex; align-items:center; gap:12px`):
   - "이전" — height48 padding0 24px radius13 배경`#FFFFFF` `box-shadow:inset 0 0 0 1.5px rgba(139,141,147,.3)` 텍스트700/14px/`#2E312E` — 위 헤더 뒤로가기와 같은 목적지(variant별 market-report/tech-report)
   - "지원사업 매칭 보기 →" — flex:1 height48 radius13 배경`#3FB6A8` hover`#0B2170` 텍스트700/14.5px/흰색 — 클릭 시 `/matching`으로 이동(지금 `handleFinish`가 `/home`으로 가던 것 대신, 프로토타입처럼 매칭 리스트로 바로 연결)

[작업 다 되면 알려줘]
새 컴포넌트/스타일 파일 만들었는지, DiagnosisStep9.tsx의 완료 화면이 이걸로 교체됐는지, "지원사업 매칭 보기 →"가 `/matching`으로 가는지만 3줄 이내로 알려줘.
