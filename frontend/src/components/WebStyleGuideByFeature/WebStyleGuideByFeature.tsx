// 기능 단위 스타일가이드 - WebStyleGuide.tsx(화면/메뉴 단위)와 같은 데이터 출처(webTokens.css)를
// 재구성한 뷰. 화면별로 반복되던 "추가 색상 토큰" 블록들을 색상/폰트색상/폰트크기/버튼/팝업
// 5개 기능 카테고리로 합치고, 어느 화면에서 쓰이는지는 각 항목의 usage 텍스트로만 표시한다.
// CSS는 WebStyleGuide와 동일한 디자인 언어라 새로 만들지 않고 그대로 재사용한다.
import styles from "../WebStyleGuide/webStyleGuide.module.css";

type ColorRole = "bg" | "text" | "border" | "other";

interface ColorToken {
  name: string;
  hex: string;
  usage: string;
  varName: string;
  role: ColorRole;
}

// WebStyleGuide.tsx의 COLORS + MATCHING_COLORS + DETAIL_COLORS + MYPAGE_COLORS +
// PROFILE_COLORS + DOCPREVIEW_COLORS + ONBOARDING_COLORS + IDEACHOICE_COLORS +
// REPORTSUMMARY_COLORS를 한데 모은 것 - 각 변수는 그쪽에서도 딱 한 번씩만 정의돼 있어서
// (재사용은 프로즈 설명으로만 언급) 합쳐도 중복 항목은 없다. role은 usage 문구 기준으로
// 배경/텍스트/테두리/기타로만 분류한 것(엄밀한 CSS 적용 검사 아님).
//
// [2026-09-14, 사용자 확인] webTokens.css에서 근접한 톤끼리 대표색 하나로 통일한 것을
// 여기도 반영 - 흡수된 항목은 배열에서 빼고, 대표색의 usage에 흡수한 용도를 같이 적었다.
//   Light Teal ← Light Teal Hover, Light Teal Hover Strong
//   Teal Mist ← Report BG, Teal Mist Hover, Card Target BG
//   Navy Mist ← AI Comment BG, Industry Anchor BG, Badge Revenue BG
//   D-day BG ← Badge Skill BG / D-day Text ← Badge Skill Text
//   Badge Download BG ← Fill History BG
//   Scrim ← Scrim Download
//   Stone Mist ← Autofill Banner BG, Delete Hover, BG Doc Preview
//   AI Comment Text ← Badge Revenue Text / Teal Green ← Badge Target Text
//   Stone Gray ← Text Placeholder / Section Subtitle ← Caption Faint
const ALL_COLORS: ColorToken[] = [
  { name: "Navy Sphere", hex: "#104A8F", usage: "주요 액션 버튼(CTA), 핵심 활성화 링크", varName: "--color-navy-sphere", role: "bg" },
  { name: "Teal Green", hex: "#0F6E62", usage: '안내 링크 텍스트, 보조 상호작용 요소 + "타깃 관점" 뱃지 텍스트 통합', varName: "--color-teal-green", role: "text" },
  { name: "Light Teal", hex: "#3FB6A8", usage: "지역칩·저장버튼 등 배경 + hover 2종(#2E9C8F, #34A296) 통합 (팔레트 등록값)", varName: "--color-light-teal", role: "bg" },
  { name: "Ink Charcoal", hex: "#2E312E", usage: "주요 텍스트, 입력란 타이틀 라벨", varName: "--color-ink-charcoal", role: "text" },
  { name: "Stone Gray", hex: "#8B8D93", usage: "서브텍스트, 버튼 테두리, 공통 인풋 테두리 + 입력란 placeholder 텍스트 통합", varName: "--color-stone-gray", role: "text" },
  { name: "Stone Mist", hex: "#EFEFF1", usage: "공통 인풋 필드 배경 + 서류 자동채움 배너/카드 삭제 hover/서류 미리보기 배경 통합", varName: "--color-stone-mist", role: "bg" },
  { name: "Border Web", hex: "#DCD8CC", usage: "구분선, 파일 업로드 점선 테두리", varName: "--color-border-web", role: "border" },
  { name: "White", hex: "#FFFFFF", usage: "앱 기본 배경, 카드 배경, 활성 버튼 텍스트", varName: "--color-white", role: "bg" },
  { name: "Scrim", hex: "rgba(0,0,0,0.3)", usage: "모달/팝업 뒤 배경 딤 + 다운로드 모달 오버레이 딤 통합", varName: "--color-scrim", role: "bg" },
  { name: "Error BG", hex: "#F2D1D1", usage: "에러 배지 배경", varName: "--color-error-bg-web", role: "bg" },
  { name: "Error Text", hex: "#C04040", usage: "에러 텍스트/보더", varName: "--color-error-text", role: "text" },
  { name: "Deep Navy", hex: "#15328C", usage: "매칭 화면 로고·기관명·카운트 숫자", varName: "--color-deep-navy", role: "text" },
  { name: "D-day BG", hex: "#F6DFAF", usage: 'D-day(모집중) 뱃지 배경 + "보유역량 활용" 뱃지 배경 통합', varName: "--color-dday-bg", role: "bg" },
  { name: "D-day Text", hex: "#8A6212", usage: 'D-day(모집중) 뱃지 텍스트 + "보유역량 활용" 뱃지 텍스트 통합', varName: "--color-dday-text", role: "text" },
  { name: "Border Nav", hex: "#EDEDF0", usage: "하단 네비게이션 상단 구분선, 카드 구분선", varName: "--color-border-nav", role: "border" },
  { name: "Tab Active Icon", hex: "#E8A93C", usage: "하단 네비 활성 탭 아이콘 stroke", varName: "--color-tab-active-icon", role: "other" },
  { name: "Tab Active Label", hex: "#B5761A", usage: "하단 네비 활성 탭 라벨", varName: "--color-tab-active-label", role: "text" },
  { name: "Section Subtitle", hex: "#B5B6BB", usage: "[draft] 업종맞춤/업종무관 그룹 제목 아래 안내문구 + AI 참고 캡션 텍스트 통합", varName: "--color-section-subtitle", role: "text" },
  { name: "AI Comment Text", hex: "#2E3A6B", usage: 'AI 코멘트 박스 라벨/본문 + "수익모델 관점" 뱃지 텍스트 통합', varName: "--color-ai-comment-text", role: "text" },
  { name: "Overview Icon", hex: "#C4841E", usage: "사업개요 카드 항목 아이콘 stroke", varName: "--color-overview-icon", role: "other" },
  { name: "Teal Mist", hex: "#DFF3EF", usage: '아바타·배지 등 배경 (팔레트 등록값) + "나의 분석 리포트" 카드, "채우기" 버튼 hover, "타깃 관점" 카드 배경 통합', varName: "--color-teal-mist", role: "bg" },
  { name: "Badge Download BG", hex: "#FFF3D6", usage: '"다운로드 가능" 뱃지 배경 + "채우기 이용내역" 카드 배경 통합', varName: "--color-badge-download-bg", role: "bg" },
  { name: "Border Dashed", hex: "rgba(139,141,147,0.3)", usage: '"+ 새 분석 시작하기" 점선 버튼 테두리 · 진단 진행바 인디케이터 배경(--color-dot-inactive는 이 값을 참조하는 별칭, 2026-09-13 통합)', varName: "--color-border-dashed", role: "border" },
  { name: "Navy Mist", hex: "#E7ECF8", usage: '"정밀 구체화" 카드 pill 배경 + AI 코멘트 박스, "업종코드를 찾았어요" 안내박스, "수익모델 관점" 뱃지 배경 통합', varName: "--color-navy-mist", role: "bg" },
  { name: "Purple Accent", hex: "#7C5CBF", usage: '4축요약카드 "차별점" 아이콘 배경', varName: "--color-purple-accent", role: "other" },
  { name: "CTA Hover Navy", hex: "#0B2170", usage: '"지원사업 매칭 보기 →" CTA 버튼 hover 배경', varName: "--color-cta-hover-navy", role: "bg" },
  { name: "Card Revenue BG", hex: "rgba(21,50,140,.05)", usage: '"수익모델 관점" 아이디어 카드 배경', varName: "--color-card-revenue-bg", role: "bg" },
  { name: "Card Skill BG", hex: "rgba(232,169,60,.08)", usage: '"보유역량 활용" 아이디어 카드 배경', varName: "--color-card-skill-bg", role: "bg" },
  { name: "Badge Target BG", hex: "#BFEAE1", usage: '"타깃 관점" 뱃지 배경', varName: "--color-badge-target-bg", role: "bg" },
  { name: "Market Density", hex: "#7A2A0A", usage: '상권분석 "동일업종 밀집도" 히트맵 그라데이션 진한 끝', varName: "--color-market-density", role: "other" },
  { name: "Industry Anchor BG", hex: "#F3F8FF", usage: '"업종코드를 찾았어요" 화면 안내박스 배경', varName: "--color-industry-anchor-bg", role: "bg" },
  { name: "Danger BG", hex: "#E0273F", usage: '마이페이지 삭제 확인 팝업 "삭제" 버튼 배경', varName: "--color-danger-bg", role: "bg" },
  { name: "Cancel BG", hex: "#ECEEF1", usage: '마이페이지 삭제 확인 팝업 "취소" 버튼 배경', varName: "--color-cancel-bg", role: "bg" },
  { name: "Cancel Text", hex: "#4B5160", usage: '마이페이지 삭제 확인 팝업 "취소" 버튼 텍스트', varName: "--color-cancel-text", role: "text" },
];

// 브랜드 전용 - UI 팔레트가 아니라 컴포넌트에 재사용 금지 (WebStyleGuide.tsx LOGO_COLORS + KAKAO_COLORS)
const BRAND_ONLY_COLORS = [
  { name: "Logo Navy", hex: "#2A3286", varName: "--logo-navy" },
  { name: "Logo Mint", hex: "#ABE0D6", varName: "--logo-mint" },
  { name: "Kakao Yellow", hex: "#FEE500", varName: "--brand-kakao-yellow" },
  { name: "Kakao Label", hex: "#391B1B", varName: "--brand-kakao-label" },
];

const ROLE_LABEL: Record<ColorRole, string> = {
  bg: "배경색",
  text: "텍스트·라벨색",
  border: "테두리·구분선",
  other: "기타(아이콘 등)",
};

// [2026-09-14, 사용자 확인] 그래프(막대·도넛·밀집도 히트맵)에 실제로 쓰이는 색만 모은 것 -
// DiagnosisReport.tsx의 RANK_BAR_COLORS / DONUT_OTHER_COLOR / getMarketDensityColor /
// getDensityColor 원본 대조. 대부분 위 01 색상 토큰을 그대로 재사용하지만(varName 있음),
// 히트맵 그라데이션 중간·옅은 끝과 도넛 "기타" 조각은 토큰 없이 코드에 값이 직접
// 하드코딩돼 있다(varName 없음 - 향후 토큰화 대상).
interface GraphColorToken {
  name: string;
  value: string;
  hex: string;
  usage: string;
  varName?: string;
}

const GRAPH_COLORS: GraphColorToken[] = [
  { name: "Rank 1st", value: "var(--color-light-teal)", hex: "#3FB6A8", usage: "막대그래프·도넛 1위 색상 (반경 500m 업종 구성 등)", varName: "--color-light-teal" },
  { name: "Rank 2nd", value: "var(--color-tab-active-icon)", hex: "#E8A93C", usage: "막대그래프·도넛 2위 색상", varName: "--color-tab-active-icon" },
  { name: "Rank 3rd", value: "var(--color-deep-navy)", hex: "#15328C", usage: "막대그래프·도넛 3위 색상", varName: "--color-deep-navy" },
  { name: "Rank 4th", value: "var(--color-purple-accent)", hex: "#7C5CBF", usage: "막대그래프·도넛 4위 색상", varName: "--color-purple-accent" },
  { name: "Donut Other", value: "rgba(139,141,147,0.35)", hex: "rgba(139,141,147,.35)", usage: '도넛 "기타" 조각 (Stone Gray 계열, 토큰 없이 하드코딩)' },
  { name: "Market Density High", value: "var(--color-market-density)", hex: "#7A2A0A", usage: "상권분석(카페형) 밀집도 히트맵 그라데이션 진한 끝(러스트)", varName: "--color-market-density" },
  { name: "Market Density Mid", value: "rgb(240,168,104)", hex: "#F0A868", usage: "상권분석(카페형) 밀집도 히트맵 그라데이션 중간 지점(55%, 토큰 없이 하드코딩)" },
  { name: "Market Density Low", value: "rgb(251,241,228)", hex: "#FBF1E4", usage: "상권분석(카페형) 밀집도 히트맵 그라데이션 옅은 끝(토큰 없이 하드코딩)" },
  { name: "Tech Density", value: "rgba(21,50,140,0.5)", hex: "#15328C", usage: "기술창업형 밀집도 히트맵 - Deep Navy 단색 + 투명도 0.1~0.8 (미리보기는 중간값 0.5)", varName: "--color-deep-navy" },
];

function GraphColorGrid({ items }: { items: GraphColorToken[] }) {
  return (
    <div className={styles.colorGrid}>
      {items.map((color) => (
        <div className={styles.colorCard} key={color.name}>
          <div className={styles.swatch} style={{ backgroundColor: color.value }} />
          <p className={styles.colorName}>{color.name}</p>
          <p className={styles.colorHex}>{color.hex}</p>
          <p className={styles.colorUsage}>{color.usage}</p>
          <span className={styles.codeLabel}>{color.varName ?? "하드코딩 (토큰 없음)"}</span>
        </div>
      ))}
    </div>
  );
}

function ColorGrid({ items }: { items: ColorToken[] }) {
  return (
    <div className={styles.colorGrid}>
      {items.map((color) => (
        <div className={styles.colorCard} key={color.varName}>
          <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
          <p className={styles.colorName}>{color.name}</p>
          <p className={styles.colorHex}>{color.hex}</p>
          <p className={styles.colorUsage}>{color.usage}</p>
          <span className={styles.codeLabel}>{color.varName}</span>
        </div>
      ))}
    </div>
  );
}

function WebStyleGuideByFeature() {
  const textColors = ALL_COLORS.filter((c) => c.role === "text");

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>MULKKO DESIGN SYSTEM · BY FEATURE</p>
        <h1 className={styles.title}>기능 단위 스타일가이드 (색상 · 폰트 · 버튼 · 팝업 · 그래프)</h1>
        <p className={styles.subheading}>
          /dev/web-style-guide(화면/메뉴 단위)와 같은 값을 색상 / 폰트 색상 / 폰트 크기 / 버튼 / 팝업 / 그래프
          6개 기능으로 재구성한 것. 화면별로 반복되던 설명은 각 항목의 사용처(usage) 문구로만 남긴다.
        </p>
      </header>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>01. 색상</h2>
        </div>
        {(Object.keys(ROLE_LABEL) as ColorRole[]).map((role) => {
          const items = ALL_COLORS.filter((c) => c.role === role);
          if (items.length === 0) return null;
          return (
            <div key={role}>
              <p className={styles.subheading}>{ROLE_LABEL[role]} ({items.length})</p>
              <ColorGrid items={items} />
            </div>
          );
        })}

        <p className={styles.subheading}>브랜드 전용 (UI 팔레트 아님 — 컴포넌트에 재사용 금지)</p>
        <div className={styles.colorGrid}>
          {BRAND_ONLY_COLORS.map((color) => (
            <div className={styles.colorCardWarning} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorWarning}>재사용 금지</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>02. 폰트 색상</h2>
        </div>
        <p className={styles.subheading}>위 01 색상 중 텍스트·라벨 용도로만 쓰이는 것만 모음 ({textColors.length}개)</p>
        <ColorGrid items={textColors} />
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>03. 폰트 크기</h2>
        </div>
        <div className={styles.typoCard}>
          <div className={styles.typoRow}>
            <span className={styles.typoTag}>LOGO</span>
            <p className={styles.logoPreview}>MULKKO</p>
            <div className={styles.typoSpec}>
              <p className={styles.typoSpecDesc}>Inter Black / 워드마크</p>
              <p className={styles.typoSpecValue}>32px / 900 / letter-spacing +1.92px</p>
            </div>
          </div>
          <div className={styles.typoRow}>
            <span className={styles.typoTag}>H1</span>
            <p className={styles.typoPreviewH1}>회원가입 / 로그인</p>
            <div className={styles.typoSpec}>
              <p className={styles.typoSpecDesc}>화면 타이틀</p>
              <p className={styles.typoSpecValue}>16px / 700</p>
            </div>
          </div>
          <div className={styles.typoRow}>
            <span className={styles.typoTag}>H2</span>
            <p className={styles.typoPreviewH2}>가입 정보 입력</p>
            <div className={styles.typoSpec}>
              <p className={styles.typoSpecDesc}>섹션 헤더</p>
              <p className={styles.typoSpecValue}>15px / 700</p>
            </div>
          </div>
          <div className={styles.typoRow}>
            <span className={styles.typoTag}>LABEL</span>
            <p className={styles.typoPreviewLabel}>이메일</p>
            <div className={styles.typoSpec}>
              <p className={styles.typoSpecDesc}>입력란 라벨</p>
              <p className={styles.typoSpecValue}>13px / 700</p>
            </div>
          </div>
          <div className={styles.typoRow}>
            <span className={styles.typoTag}>BODY</span>
            <p className={styles.typoPreviewBody}>다람쥐 헌 쳇바퀴에 타고파</p>
            <div className={styles.typoSpec}>
              <p className={styles.typoSpecDesc}>본문/값</p>
              <p className={styles.typoSpecValue}>14px / 400</p>
            </div>
          </div>
          <div className={styles.typoRow}>
            <span className={styles.typoTag}>CAPTION</span>
            <p className={styles.typoPreviewCaption}>비밀번호를 잊으셨나요?</p>
            <div className={styles.typoSpec}>
              <p className={styles.typoSpecDesc}>캡션/링크</p>
              <p className={styles.typoSpecValue}>11px / 400</p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>04. 버튼</h2>
        </div>
        <div className={styles.componentCard}>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <button type="button" className={styles.btnPrimaryCta}>로그인</button>
              <span className={styles.codeLabel}>Primary CTA · 로그인/회원가입 · 368×54 · radius 14px</span>
            </div>
            <div className={styles.componentItem}>
              <a href="#none" className={styles.linkForgot}>비밀번호를 잊으셨나요?</a>
              <span className={styles.codeLabel}>텍스트 링크형 · Teal Green · 12px</span>
            </div>
            <div className={styles.componentItem}>
              <a href="#none" className={styles.linkSignup}>회원가입</a>
              <span className={styles.codeLabel}>텍스트 링크형 · Navy Sphere · Bold 13px</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <button type="button" className={styles.matchLoadMoreButton}>더보기</button>
              <span className={styles.codeLabel}>매칭 리스트 더보기 · --color-teal-green · --shadow-inset-gray</span>
            </div>
            <div className={styles.componentItem}>
              <span className={styles.detailFillButton}>
                채우기 <span aria-hidden="true">›</span>
              </span>
              <span className={styles.codeLabel}>공고 상세 "채우기" 필버튼 · --color-teal-mist</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.detailCtaRow}>
                <span className={styles.detailApplyOff}>지원 시 체크</span>
                <span className={styles.detailApplyOn}>✓ 지원함</span>
                <span className={styles.detailHomeButton}>원 공고 홈페이지로 이동</span>
              </div>
              <span className={styles.codeLabel}>공고 상세 하단 CTA · 토글 off/on + 홈 이동 · --radius-cta</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <button type="button" className={styles.onboardingCta}>다음</button>
              <span className={styles.codeLabel}>온보딩 "다음" CTA · --radius-input · --shadow-onboarding-cta</span>
            </div>
            <div className={styles.componentItem}>
              <button type="button" className={styles.onboardingChoiceCard}>
                <span className={styles.onboardingChoiceCardTitle}>사업 아이디어를 구상하고 싶어요</span>
                <span className={styles.onboardingChoiceCardDesc}>카드형 버튼 (선택지)</span>
              </button>
              <span className={styles.codeLabel}>온보딩/진단선택 카드형 버튼 · --radius-onboarding-card</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>05. 팝업</h2>
        </div>
        <div className={styles.componentCard}>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.toastPreview}>저장되었습니다</div>
              <span className={styles.codeLabel}>Toast · 하단 팝업 · 자동 사라짐</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.modalPreview}>
                <div className={styles.modalPreviewPanel}>
                  <div className={styles.modalPreviewHeader}>
                    <span className={styles.modalPreviewTitle}>서비스 이용약관</span>
                    <span className={styles.modalPreviewClose}>✕</span>
                  </div>
                  <p className={styles.modalPreviewBody}>약관 보기 팝업 (X · 배경 클릭 · Esc로 닫힘)</p>
                </div>
              </div>
              <span className={styles.codeLabel}>회원가입 약관 모달 · --color-scrim · radius 12px</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <p className={styles.colorUsage}>
                서류 미리보기 "다운로드" 모달 — 별도 프리뷰 없이 토큰만 존재: --radius-modal(18px),
                --shadow-modal(0 24px 50px -20px rgba(21,50,140,.4)), 배경 딤은 --color-scrim-download
              </p>
              <span className={styles.codeLabel}>다운로드 모달 (스펙만, 라이브 프리뷰 없음)</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.confirmPreviewCard}>
                <p className={styles.confirmPreviewText}>
                  이 공고를 삭제할까요?
                  <br />
                  나의 관심있는 지원사업에서 사라지고, 다시 불러올 수 없어요.
                </p>
                <div className={styles.confirmPreviewButtons}>
                  <span className={styles.confirmPreviewCancelBtn}>취소</span>
                  <span className={styles.confirmPreviewDeleteBtn}>삭제</span>
                </div>
              </div>
              <span className={styles.codeLabel}>
                마이페이지 삭제 확인 팝업 · --radius-confirm-card · --shadow-confirm-card · 배경 딤은
                --color-scrim-download 재사용
              </span>
            </div>
            <div className={styles.componentItem}>
              <div className={styles.toastPreview}>나의 관심있는 지원사업에서 삭제됐어요.</div>
              <span className={styles.codeLabel}>
                삭제 완료 토스트 · 위 Toast와 동일 스펙(1.5초 후 자동 소멸)
              </span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>06. 그래프</h2>
        </div>
        <p className={styles.subheading}>
          막대그래프·도넛차트·밀집도 히트맵(DiagnosisReport.tsx)에서 실제로 쓰이는 색만 모음 ({GRAPH_COLORS.length}개)
        </p>
        <GraphColorGrid items={GRAPH_COLORS} />
      </section>
    </div>
  );
}

export default WebStyleGuideByFeature;
