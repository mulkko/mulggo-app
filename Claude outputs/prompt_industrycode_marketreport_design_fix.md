[작업 배경]
`frontend/src/pages/diagnosis/` 안의 12(업종코드 매칭)·13(상권분석 리포트) 화면을 프로토타입과 대조 검토했다.
카드 문구·데이터 연동 자체는 문제없지만, 아래 2가지가 프로토타입 디자인과 다르다. 이번 라운드는 이 2가지만 고친다 — `ksicCode`를 실제로 어떻게 받아오는지(연동 방식) 자체는 이번엔 건드리지 않는다. 지금 이미 diagnosisAnswers에 저장돼 있는 값이나, `/analysis/market` 응답에 이미 내려오는 필드를 "화면에 어떻게 그리느냐"만 고치는 작업이다.

[레퍼런스]
프로토타입 파일: `docs/260910_2008_Mulkko Prototype (standalone).html`. grep 키: `is.code` (12번, 업종코드 매칭 실제 화면 블록 — 파일에 `is.code }}`가 2번 나오는데 **두 번째**가 실제 화면), `is.reportA` (13번, 상권분석 리포트, 마찬가지로 두 번째 등장이 실제 화면).
"프로토타입 검토 원칙" 등 토큰 절약 원칙은 항상 적용 — 아래 [실측 디자인 값]에 없는 부분만 파일에서 확인.

---

## 1) 업종코드 매칭 결과 카드 스타일 (`DiagnosisIndustryCode.tsx`)

지금은 Q2/Q5 선택 화면과 같은 `diagnosisStyles.radioCard`(inset border 스타일)를 그대로 쓰고 있는데, 프로토타입의 이 화면 카드는 **완전히 다른 스타일**(테두리 없이 navy 톤 드롭섀도우)이다. `styles/diagnosisIndustryCode.module.css`(이미 이 화면 전용 스타일시트가 있음)에 새 클래스를 추가하고, `codeOptions.map(...)` 부분에서 `diagnosisStyles.radioCard` 대신 이 새 클래스를 쓰도록 교체해줘.

[실측 디자인 값] (`qMeta`가 아니라 `is.code`의 `matchedCodes` 카드 블록, sc-for 리스트)
- 카드: `border-radius:16px`(기존 `--radius-onboarding-card` 토큰과 같은 값이니 그대로 재사용), `padding:20px`, `box-shadow: 0 10px 26px -20px rgba(21,50,140,.6)`, hover `0 10px 26px -20px rgba(21,50,140,.9)` — **inset 테두리 없음**, 순수 드롭섀도우
- 카드 내부: 상단 줄(`display:flex; align-items:center; justify-content:space-between; gap:10px`)에 업종명(`font-weight:700; font-size:16px; color:#2E312E`)과 우측 라디오 원(18x18, `border:1.5px solid rgba(139,141,147,.3)`, 원형, 선택 시 안쪽에 10x10 `background:#15328C` 원)
- 하단 줄: 업종코드 텍스트 `font-size:13px; color:#8B8D93` (현재 코드의 `업종코드 {code}` 문구는 그대로 유지)
- 하단 "이전"/"분석 리포트 보러가기 →" 버튼은 지금 쓰는 `diagnosisStyles.prevButton`/`nextButton` 그대로 두면 됨(이미 프로토타입과 일치) — 카드 스타일만 교체 대상.

## 2) 상권분석 리포트 "동일업종 밀집도" 히트맵 (`DiagnosisMarketReport.tsx`)

지금은 이 섹션이 `<p>업종코드 확인 후 표시돼요.</p>` 플레이스홀더 문구만 보여주고, `MarketReportData.density`(타입은 `unknown | null`로만 선언돼 있고 실제로 안 씀) 필드를 전혀 렌더링하지 않고 있다. 프로토타입엔 이 자리에 실제 5×5 히트맵이 있다.

**먼저 확인할 것**: `GET /analysis/market` 응답의 `density` 필드가 실제로 어떤 모양(구조)으로 오는지 백엔드 코드(`backend/api/analysis.py` 등, 실제 파일명은 찾아서)에서 확인해줘. `DiagnosisTechReport.tsx`의 `DensityGrid`(`grid_cols`/`grid_rows`/`cells:[{x,y,count,sigungu}]`/`total_sigungu_count`/`shown_sigungu_count`)와 비슷한 구조로 이미 내려오고 있다면 그 타입을 참고해서 `MarketReportData.density`도 같은 형태로 타입을 채우고 렌더링하면 된다. 만약 실제로 값이 없거나(`null`) 아직 백엔드가 안 내려주는 상태라면, **이번엔 백엔드나 ksicCode 연동 자체는 건드리지 말고** 지금처럼 플레이스홀더 문구를 유지한 채 이 항목은 스킵해도 된다 — 억지로 값을 만들어내지 말 것.

값이 실제로 있어서 그린다면, 아래 [실측 디자인 값]대로 — **기술창업 리포트(`DiagnosisTechReport.tsx`)의 `DensityGridView`와 색상 팔레트·격자 크기가 다르다는 점 주의** (거긴 6×3 네이비 팔레트, 여긴 5×5 주황/갈색 팔레트). 완전히 새 컴포넌트로 만들어도 되고, `DensityGridView`를 grid_cols/grid_rows/색상을 props로 받게 확장해도 됨 — 구현 방식은 알아서 판단.

[실측 디자인 값] (`is.reportA`의 "동일업종 밀집도" 섹션)
- 섹션 카드: 기존 `.sectionCard`(흰배경, radius14, padding16, inset shadow `#E3E3E6`) 그대로, 제목 "동일업종 밀집도"(14px/700/`#2E312E`) + 부제 "{동} 반경 500m {업종명}({업종코드}) 밀집도" 형식(11px, 가운데정렬, `#2E312E`) — 부제의 동/업종명/코드는 실제 diagnosisAnswers 값으로 채울 것
- 격자: `grid-template-columns:repeat(5,1fr); grid-template-rows:repeat(5,1fr); gap:3px`, 전체 높이 126px. 셀 색상: 값 0 또는 없음 = `#FBF1E4`(연한 살구), 값 있을 때는 `count/maxCount` 비율에 따라 `#FBF1E4` → `#F0A868`(중간) → `#7A2A0A`(진한 갈색) 그라데이션 보간 — 값이 있는 셀은 가운데에 숫자(10px/800/흰색) 표시
- "내 위치" 마커: 백엔드가 내 위치에 해당하는 셀 좌표(x,y 또는 이와 동등한 필드)를 함께 내려줄 때만 표시 — 격자 위에 절대위치로 10x10 `#2E312E` 원(흰 테두리 1.5px) + 바로 아래 "내 위치" 라벨(8.5px). **좌표를 내려주는 필드가 없으면 이 마커는 만들지 말고 생략**(프로토타입 값은 예시 하드코딩이라 실제 좌표 없이 임의로 위치를 지어내면 안 됨)
- 오른쪽 범례: 세로 그라데이션 바(12px 너비, `linear-gradient(to bottom, #7A2A0A, #F0A868 55%, #FBF1E4)`) + 옆에 눈금 숫자 4~5개(실제 maxCount 기준으로 등분해서 계산, 프로토타입의 "8,6,4,2,0"은 예시 값이니 그대로 베끼지 말 것) + 세로 텍스트 "사업체 수"(8px, `writing-mode:vertical-rl`)
- 하단 캡션 2줄(11px, `#8B8D93`, line-height1.6): "* 진한 색일수록 동일업종 밀집" + 원형 마커 범례, "* 실제 지도가 아닌 상대적 밀집도를 표현한 도식입니다." / "* 상위 N개 지역 기준 (전체 M개 지역 중)" — N/M은 백엔드가 내려주는 shown/total 카운트 필드로 채울 것(필드명은 실제 응답 보고 맞출 것)

[작업 다 되면 알려줘]
1과 2 각각 적용됐는지, 2번은 실제로 데이터가 있어서 그렸는지 아니면 데이터가 없어서 스킵했는지만 3줄 이내로 알려줘.
