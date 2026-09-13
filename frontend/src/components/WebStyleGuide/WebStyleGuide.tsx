import styles from "./webStyleGuide.module.css";

const COLORS = [
  { name: "Navy Sphere", hex: "#104A8F", usage: "주요 액션 버튼(CTA), 핵심 활성화 링크", varName: "--color-navy-sphere" },
  { name: "Teal Green", hex: "#0F6E62", usage: "안내 링크 텍스트, 보조 상호작용 요소", varName: "--color-teal-green" },
  { name: "Light Teal", hex: "#3FB6A8", usage: "컬러 팔레트 등록값 (용도 팀 확인 필요)", varName: "--color-light-teal" },
  { name: "Teal Mist", hex: "#DFF3EF", usage: "컬러 팔레트 등록값 (용도 팀 확인 필요)", varName: "--color-teal-mist" },
  { name: "Ink Charcoal", hex: "#2E312E", usage: "주요 텍스트, 입력란 타이틀 라벨", varName: "--color-ink-charcoal" },
  { name: "Stone Gray", hex: "#8B8D93", usage: "서브텍스트, 버튼 테두리, 공통 인풋 테두리", varName: "--color-stone-gray" },
  { name: "Text Placeholder", hex: "#757575", usage: "입력란 placeholder 텍스트", varName: "--color-text-placeholder" },
  { name: "Stone Mist", hex: "#EFEFF1", usage: "공통 인풋 필드 배경", varName: "--color-stone-mist" },
  { name: "Border Web", hex: "#DCD8CC", usage: "구분선, 파일 업로드 점선 테두리", varName: "--color-border-web" },
  { name: "White", hex: "#FFFFFF", usage: "앱 기본 배경, 카드 배경, 활성 버튼 텍스트", varName: "--color-white" },
  { name: "Scrim", hex: "rgba(0,0,0,0.3)", usage: "모달/팝업 뒤 배경 딤", varName: "--color-scrim" },
  { name: "Error BG", hex: "#F2D1D1", usage: "에러 배지 배경", varName: "--color-error-bg-web" },
  { name: "Error Text", hex: "#C04040", usage: "에러 텍스트/보더", varName: "--color-error-text" },
];

const LOGO_COLORS = [
  { name: "Logo Navy", hex: "#2A3286", varName: "--logo-navy" },
  { name: "Logo Mint", hex: "#ABE0D6", varName: "--logo-mint" },
];

// 매칭 리스트(공고 리스트) 화면에서 추가된 색상 토큰
const MATCHING_COLORS = [
  { name: "Deep Navy", hex: "#15328C", usage: "매칭 화면 로고·기관명·카운트 숫자", varName: "--color-deep-navy" },
  { name: "D-day BG", hex: "#F6DFAF", usage: "D-day(모집중) 뱃지 배경", varName: "--color-dday-bg" },
  { name: "D-day Text", hex: "#8A6212", usage: "D-day(모집중) 뱃지 텍스트", varName: "--color-dday-text" },
  { name: "Border Nav", hex: "#EDEDF0", usage: "하단 네비게이션 상단 구분선", varName: "--color-border-nav" },
  { name: "Tab Active Icon", hex: "#E8A93C", usage: "하단 네비 활성 탭 아이콘 stroke", varName: "--color-tab-active-icon" },
  { name: "Tab Active Label", hex: "#B5761A", usage: "하단 네비 활성 탭 라벨", varName: "--color-tab-active-label" },
  { name: "Section Subtitle", hex: "#B5B6BB", usage: "[draft] 업종맞춤/업종무관 그룹 제목 아래 안내문구", varName: "--color-section-subtitle" },
];

// 공고 상세(지원사업 상세) 화면에서 추가된 색상 토큰
const DETAIL_COLORS = [
  { name: "AI Comment BG", hex: "#EEF1FA", usage: "AI 코멘트 박스 배경", varName: "--color-ai-comment-bg" },
  { name: "AI Comment Text", hex: "#2E3A6B", usage: "AI 코멘트 박스 라벨/본문", varName: "--color-ai-comment-text" },
  { name: "Overview Icon", hex: "#C4841E", usage: "사업개요 카드 항목 아이콘 stroke", varName: "--color-overview-icon" },
  { name: "Autofill Banner BG", hex: "#FAFAF9", usage: "서류 자동채움 안내 배너 배경", varName: "--color-autofill-banner-bg" },
  { name: "Teal Mist Hover", hex: "#CDEDE6", usage: '"채우기" 필 버튼 hover 배경', varName: "--color-teal-mist-hover" },
  { name: "Light Teal Hover", hex: "#2E9C8F", usage: '"원 공고 홈페이지로 이동" 버튼 hover 배경', varName: "--color-light-teal-hover" },
];

// 마이페이지 화면에서 추가된 색상 토큰
const MYPAGE_COLORS = [
  { name: "Report BG", hex: "#EAF7F4", usage: '"나의 분석 리포트" 카드 배경', varName: "--color-report-bg" },
  { name: "Fill History BG", hex: "#FDF6E7", usage: '"채우기 이용내역" 카드 배경', varName: "--color-fill-history-bg" },
  { name: "Badge Download BG", hex: "#FFF3D6", usage: '"다운로드 가능" 뱃지 배경', varName: "--color-badge-download-bg" },
  { name: "Border Dashed", hex: "rgba(139,141,147,0.3)", usage: '"+ 새 분석 시작하기" 점선 버튼 테두리', varName: "--color-border-dashed" },
  { name: "Delete Hover", hex: "rgba(139,141,147,0.15)", usage: "카드 삭제(X) 버튼 hover 배경", varName: "--color-delete-hover" },
];

// 프로필 수정 화면에서 추가된 색상 토큰
const PROFILE_COLORS = [
  {
    name: "Light Teal Hover Strong",
    hex: "#34A296",
    usage: '"저장하기" 버튼 hover 배경 (공고 상세 CTA의 #2E9C8F와 다른 값)',
    varName: "--color-light-teal-hover-strong",
  },
];

// 프로필 수정 화면 V2(/edit-v2)에서 추가된 색상 토큰
const PROFILE_V2_COLORS = [
  { name: "Mist Alt", hex: "#F5F5F7", usage: "인풋 배경 (기존 Stone Mist #EFEFF1과 다른 값)", varName: "--color-mist-alt" },
  { name: "BG Hover Mist", hex: "#F8F8FA", usage: "사업자등록증 업로드 박스 hover 배경", varName: "--color-bg-hover-mist" },
];

// 서류 미리보기 화면에서 추가된 색상 토큰
const DOCPREVIEW_COLORS = [
  { name: "BG Doc Preview", hex: "#F7F7F8", usage: "서류 미리보기 본문·헤더 배경", varName: "--color-bg-doc-preview" },
  { name: "Scrim Download", hex: "rgba(23,26,25,0.45)", usage: "다운로드 모달 오버레이 딤 (--color-scrim보다 진함)", varName: "--color-scrim-download" },
];

// 카카오톡 브랜드 전용 (UI 팔레트 아님)
const KAKAO_COLORS = [
  { name: "Kakao Yellow", hex: "#FEE500", varName: "--brand-kakao-yellow" },
  { name: "Kakao Label", hex: "#391B1B", varName: "--brand-kakao-label" },
];

// 온보딩 화면에서 추가된 색상 토큰
const ONBOARDING_COLORS = [
  { name: "Dot Inactive", hex: "rgba(139,141,147,0.3)", usage: "페이지 인디케이터 비활성 점 배경", varName: "--color-dot-inactive" },
];

// 진단 방식 선택 화면(05-1)에서 추가된 색상 토큰
const IDEACHOICE_COLORS = [
  { name: "Navy Mist", hex: "#E7ECF8", usage: '"정밀 구체화" 카드 pill 배경 (Teal Mist의 네이비 버전)', varName: "--color-navy-mist" },
];

// 사업구체화 리포트 요약 화면(13-1/14-2, is.reportASum/is.reportBSum)에서 추가된 색상 토큰
const REPORTSUMMARY_COLORS = [
  { name: "Purple Accent", hex: "#7C5CBF", usage: "4축요약카드 \"차별점\" 아이콘 배경", varName: "--color-purple-accent" },
  { name: "CTA Hover Navy", hex: "#0B2170", usage: '"지원사업 매칭 보기 →" CTA 버튼 hover 배경', varName: "--color-cta-hover-navy" },
  { name: "Caption Faint", hex: "#A9ABB2", usage: "AI 참고 캡션 텍스트", varName: "--color-caption-faint" },
  { name: "Card Target BG", hex: "rgba(63,182,168,.06)", usage: '"타깃 관점" 아이디어 카드 배경', varName: "--color-card-target-bg" },
  { name: "Card Revenue BG", hex: "rgba(21,50,140,.05)", usage: '"수익모델 관점" 아이디어 카드 배경', varName: "--color-card-revenue-bg" },
  { name: "Card Skill BG", hex: "rgba(232,169,60,.08)", usage: '"보유역량 활용" 아이디어 카드 배경', varName: "--color-card-skill-bg" },
  { name: "Badge Target BG", hex: "#BFEAE1", usage: '"타깃 관점" 뱃지 배경', varName: "--color-badge-target-bg" },
  { name: "Badge Target Text", hex: "#0B5A50", usage: '"타깃 관점" 뱃지 텍스트', varName: "--color-badge-target-text" },
  { name: "Badge Revenue BG", hex: "#C9D6F6", usage: '"수익모델 관점" 뱃지 배경', varName: "--color-badge-revenue-bg" },
  { name: "Badge Revenue Text", hex: "#102569", usage: '"수익모델 관점" 뱃지 텍스트', varName: "--color-badge-revenue-text" },
  { name: "Badge Skill BG", hex: "#F3DA9B", usage: '"보유역량 활용" 뱃지 배경', varName: "--color-badge-skill-bg" },
  { name: "Badge Skill Text", hex: "#714800", usage: '"보유역량 활용" 뱃지 텍스트', varName: "--color-badge-skill-text" },
];

function WebStyleGuide() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>MULKKO DESIGN SYSTEM</p>
        <h1 className={styles.title}>공통 UI 스타일가이드 (로그인 · 회원가입)</h1>
      </header>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>01. COLOR PALETTE</h2>
        </div>
        <div className={styles.colorGrid}>
          {COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>

        <p className={styles.subheading}>로고 전용 (UI 팔레트와 분리 — 컴포넌트에 재사용 금지)</p>
        <div className={styles.colorGrid}>
          {LOGO_COLORS.map((color) => (
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
          <h2 className={styles.sectionTitle}>02. TYPOGRAPHY SYSTEM</h2>
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
              <p className={styles.typoSpecValue}>13.5px / 400</p>
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
          <h2 className={styles.sectionTitle}>03. INPUT FIELD (공통 통합 스펙)</h2>
        </div>
        <div className={styles.componentCard}>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.inputDefault}>example@email.com</div>
              <span className={styles.codeLabel}>DEFAULT</span>
            </div>
            <div className={styles.componentItem}>
              <div className={styles.inputFocused}>example@email.com</div>
              <span className={styles.codeLabel}>FOCUSED</span>
            </div>
            <div className={styles.componentItem}>
              <div className={styles.inputError}>invalid-email</div>
              <p className={styles.inputErrorHelp}>* 올바른 이메일 형식이 아닙니다</p>
              <span className={styles.codeLabel}>ERROR</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>04. 버튼 & 인터랙션</h2>
        </div>
        <div className={styles.componentCard}>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <button type="button" className={styles.btnPrimaryCta}>로그인</button>
              <span className={styles.codeLabel}>Primary CTA · 368×54 · radius 14px</span>
            </div>
            <div className={styles.componentItem}>
              <a href="#none" className={styles.linkForgot}>비밀번호를 잊으셨나요?</a>
              <span className={styles.codeLabel}>Teal Green · 12px</span>
            </div>
            <div className={styles.componentItem}>
              <a href="#none" className={styles.linkSignup}>회원가입</a>
              <span className={styles.codeLabel}>Navy Sphere · Bold 13px</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.fileUpload}>+ 사업자등록증 첨부 (선택)</div>
              <span className={styles.codeLabel}>점선 테두리 · Border Web</span>
            </div>
            <div className={styles.componentItem}>
              <div className={styles.toastPreview}>저장되었습니다</div>
              <span className={styles.codeLabel}>Toast · Heavy Metal 배경 · 하단 팝업</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.checkboxRow}>
                <span className={styles.checkboxOn} />
                <span className={styles.checkboxOff} />
                <span className={styles.checkboxOffNavy} />
              </div>
              <span className={styles.codeLabel}>체크박스 · radius 6px (--radius-check) · ON: Navy Sphere</span>
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
              <span className={styles.codeLabel}>Modal · Scrim 배경(--color-scrim) · radius 12px</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>05. 간격 & 레이아웃</h2>
        </div>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>기본 외부 마진</span><span>24px</span></div>
          <div className={styles.specRow}><span>로그인 세부 간격</span><span>14px</span></div>
          <div className={styles.specRow}><span>회원가입 디테일 간격</span><span>10px</span></div>
          <div className={styles.specRow}><span>모바일 표준 가로폭</span><span>420px (최대 제한)</span></div>
          <div className={styles.specRow}><span>안전 영역 코너 반경</span><span>28px</span></div>
          <div className={styles.specRow}><span>앱 섀도우</span><span>Drop Shadow · 60px Blur · Navy Sphere 35%</span></div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>06. 매칭 리스트 (공고 리스트)</h2>
        </div>

        <p className={styles.subheading}>추가 색상 토큰</p>
        <div className={styles.colorGrid}>
          {MATCHING_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>

        <p className={styles.subheading}>공고 카드 · 뱃지 · 칩</p>
        <div className={styles.componentCard}>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.matchCard}>
                <div className={styles.matchCardTop}>
                  <span className={styles.matchAgency}>중소벤처기업부</span>
                  <span className={styles.matchDday}>모집중 D-6</span>
                </div>
                <span className={styles.matchTitle}>2026년 청년 소상공인 창업 자금 지원</span>
                <div className={styles.matchTagRow}>
                  <span className={styles.matchTag}>#청년창업</span>
                  <span className={styles.matchTag}>#소상공인</span>
                </div>
              </div>
              <span className={styles.codeLabel}>Card · radius 12px · --shadow-card / --shadow-card-hover</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <span className={styles.matchRegionChip}>마포구 기준</span>
              <span className={styles.codeLabel}>지역 필터 칩 · --color-light-teal · --radius-pill</span>
            </div>
            <div className={styles.componentItem}>
              <span className={styles.matchDropdownChip}>업종 전체 ▾</span>
              <span className={styles.codeLabel}>드롭다운 칩 · --shadow-inset-gray</span>
            </div>
            <div className={styles.componentItem}>
              <div className={styles.matchCountBox}>
                <span className={styles.matchCountLabel}>총 매칭 사업</span>
                <span className={styles.matchCountValue}>5건</span>
              </div>
              <span className={styles.codeLabel}>카운트 박스 · --shadow-inset-navy</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <button type="button" className={styles.matchLoadMoreButton}>더보기</button>
              <span className={styles.codeLabel}>더보기 버튼 · --color-teal-green · --shadow-inset-gray · --radius-input</span>
            </div>
          </div>
        </div>

        <p className={styles.subheading}>하단 네비게이션 (BottomNav)</p>
        <div className={styles.componentCard}>
          <div className={styles.bottomNavPreview}>
            <div className={`${styles.bottomNavTab} ${styles.bottomNavTabActive}`}>◆<span>매칭</span></div>
            <div className={styles.bottomNavTab}>◇<span>홈</span></div>
            <div className={styles.bottomNavTab}>◇<span>아이디어</span></div>
            <div className={styles.bottomNavTab}>◇<span>마이페이지</span></div>
          </div>
          <span className={styles.codeLabel}>높이 74px · 상단 border --color-border-nav · 활성: --color-tab-active-label</span>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>07. 공고 상세 (지원사업 상세)</h2>
        </div>

        <p className={styles.subheading}>추가 색상 토큰</p>
        <div className={styles.colorGrid}>
          {DETAIL_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>
        <p className={styles.subheading}>
          북마크 채움색은 --color-tab-active-icon, AI 코멘트 제목색은 --color-deep-navy,
          카드 구분선은 --color-border-nav 재사용
        </p>

        <p className={styles.subheading}>추가 radius / shadow 토큰</p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--radius-card</span><span>14px (AI 코멘트·사업개요·공고내용·신청서류 카드)</span></div>
          <div className={styles.specRow}><span>--radius-cta</span><span>13px (하단 CTA 버튼 2개)</span></div>
          <div className={styles.specRow}><span>--shadow-inset-ai-comment</span><span>inset 0 0 0 1.2px rgba(21,50,140,.25)</span></div>
          <div className={styles.specRow}><span>--shadow-inset-card</span><span>inset 0 0 0 1.2px rgba(139,141,147,.25)</span></div>
          <div className={styles.specRow}><span>--shadow-inset-teal</span><span>inset 0 0 0 1px #3FB6A8 (신청서류 카드)</span></div>
          <div className={styles.specRow}><span>--shadow-inset-gray-strong</span><span>inset 0 0 0 1.5px rgba(139,141,147,.3) ("지원 시 체크")</span></div>
        </div>

        <p className={styles.subheading}>AI 코멘트 박스 · 카드 · CTA</p>
        <div className={styles.componentCard}>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.detailAiBox}>
                <span className={styles.detailAiTitle}>AI 코멘트</span>
                <p className={styles.detailAiBody}>
                  지역가산(마포구), 청년가산(만 39세 이하) 조건이 회원님 상황에 적합해요.
                </p>
              </div>
              <span className={styles.codeLabel}>AI 코멘트 박스 · --radius-card · --shadow-inset-ai-comment</span>
            </div>
            <div className={styles.componentItem}>
              <div className={styles.detailCard}>
                <span className={styles.detailCardTitle}>공고 내용</span>
                <p className={styles.detailCardBody}>흰 배경 카드 · inset 테두리로 경계 표현</p>
              </div>
              <span className={styles.codeLabel}>사업개요/공고내용 카드 · --shadow-inset-card</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <span className={styles.detailFillButton}>
                채우기 <span aria-hidden="true">›</span>
              </span>
              <span className={styles.codeLabel}>"채우기" 필 버튼 · --color-teal-mist / hover --color-teal-mist-hover</span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.detailCtaRow}>
                <span className={styles.detailApplyOff}>지원 시 체크</span>
                <span className={styles.detailApplyOn}>✓ 지원함</span>
                <span className={styles.detailHomeButton}>원 공고 홈페이지로 이동</span>
              </div>
              <span className={styles.codeLabel}>하단 CTA · 높이 50px · --radius-cta · 토글 off/on + 홈 이동</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>08. 마이페이지</h2>
        </div>

        <p className={styles.subheading}>추가 색상 토큰</p>
        <div className={styles.colorGrid}>
          {MYPAGE_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>
        <p className={styles.subheading}>
          분석 리포트 제목색은 --color-teal-green, "채우기" 설명 텍스트는 --color-dday-text,
          "다운로드 가능" 뱃지 텍스트는 --color-tab-active-icon, "지원함" 뱃지는
          --color-teal-green + --color-teal-mist 재사용. 프로필 요약 카드 테두리는
          --shadow-inset-card, 관심 지원사업 카드는 공통 컴포넌트 AnnouncementCard 재사용.
        </p>

        <p className={styles.subheading}>추가 radius / shadow 토큰</p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--radius-cta</span><span>13px (분석 리포트 · 채우기 이용내역 · 지원내역 카드)</span></div>
          <div className={styles.specRow}><span>--shadow-inset-report</span><span>inset 0 0 0 1.2px rgba(63,182,168,.35) (분석 리포트 카드)</span></div>
          <div className={styles.specRow}><span>--shadow-inset-report-hover</span><span>inset 0 0 0 1.2px #3FB6A8 (분석 리포트 카드 hover)</span></div>
          <div className={styles.specRow}><span>--shadow-inset-amber</span><span>inset 0 0 0 1.2px rgba(232,169,60,.45) (채우기 이용내역 카드)</span></div>
          <div className={styles.specRow}><span>--shadow-inset-neutral</span><span>inset 0 0 0 1.2px #E3E3E6 (나의 지원내역 카드)</span></div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>09. 프로필 수정</h2>
        </div>

        <p className={styles.subheading}>추가 색상 토큰</p>
        <div className={styles.colorGrid}>
          {PROFILE_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>
        <p className={styles.subheading}>
          인풋 배경은 --color-stone-mist, 아바타 배경은 --color-teal-mist, "사진 변경" 텍스트는
          --color-teal-green, 구분선은 --color-border-nav, select 화살표·서브텍스트는
          --color-stone-gray, 숫자·이메일 Inter 폰트는 --font-family-logo, "저장하기" 버튼 배경은
          --color-light-teal 재사용.
        </p>

        <p className={styles.subheading}>추가 크기 / radius 토큰</p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--input-height-form</span><span>48px (인풋·select 공통 높이)</span></div>
          <div className={styles.specRow}><span>--btn-height-save</span><span>52px ("저장하기" 버튼 높이)</span></div>
          <div className={styles.specRow}><span>--radius-thumb</span><span>9px (사업자등록증 업로드 행 썸네일)</span></div>
          <div className={styles.specRow}><span>--radius-input</span><span>12px (인풋·select) — 재사용</span></div>
          <div className={styles.specRow}><span>--radius-cta</span><span>13px ("저장하기" 버튼) — 재사용</span></div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>09-1. 프로필 수정 V2 (/edit-v2)</h2>
        </div>

        <p className={styles.subheading}>
          기존 프로필 수정(/mypage/edit)과 별도 화면 — 항목 구성만 다르고 레이아웃 스펙은
          동일 계열. 인풋 배경/테두리만 근소하게 다른 값이라 아래 토큰으로 분리했다.
        </p>
        <div className={styles.colorGrid}>
          {PROFILE_V2_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>
        <p className={styles.subheading}>
          select 화살표는 --color-teal-green, 업로드 박스 테두리는 --color-border-dashed,
          hover 테두리는 --color-light-teal, 구분선은 --color-border-nav, "저장하기" 버튼은
          --color-light-teal + hover --color-light-teal-hover-strong 재사용.
        </p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--shadow-inset-gray-soft</span><span>inset 0 0 0 1.5px rgba(139,141,147,.22) (인풋 테두리)</span></div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>10. 서류 미리보기</h2>
        </div>

        <p className={styles.subheading}>추가 색상 토큰</p>
        <div className={styles.colorGrid}>
          {DOCPREVIEW_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>

        <p className={styles.subheading}>카카오톡 브랜드 전용 (UI 팔레트 아님 — 컴포넌트에 재사용 금지)</p>
        <div className={styles.colorGrid}>
          {KAKAO_COLORS.map((color) => (
            <div className={styles.colorCardWarning} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorWarning}>재사용 금지</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>

        <p className={styles.subheading}>
          "나의 정보로 채우기" CTA·모달 "로컬 저장소에 저장하기" 버튼 배경은 --color-light-teal +
          hover --color-light-teal-hover-strong, 아이콘 원 배경은 --color-white + --shadow-inset-card,
          문서 아이콘 stroke·설명 텍스트는 --color-stone-gray, 제목은 --color-ink-charcoal 재사용.
        </p>

        <p className={styles.subheading}>추가 radius / shadow 토큰</p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--radius-modal</span><span>18px (다운로드 모달 카드)</span></div>
          <div className={styles.specRow}><span>--shadow-modal</span><span>0 24px 50px -20px rgba(21,50,140,.4) (다운로드 모달 카드)</span></div>
          <div className={styles.specRow}><span>--radius-cta</span><span>13px (CTA·모달 버튼) — 재사용</span></div>
          <div className={styles.specRow}><span>--radius-input</span><span>12px (모달 하단 버튼) — 재사용</span></div>
          <div className={styles.specRow}><span>--btn-height-save</span><span>52px (CTA 높이) — 재사용</span></div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>11. 온보딩</h2>
        </div>

        <p className={styles.subheading}>추가 색상 토큰</p>
        <div className={styles.colorGrid}>
          {ONBOARDING_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>
        <p className={styles.subheading}>
          마스코트 원 배경은 --color-teal-mist, 배지는 --color-teal-mist + --color-teal-green +
          --radius-pill, 현재 페이지 인디케이터 점은 --color-deep-navy, "다음" CTA 버튼은
          --color-light-teal / hover --color-light-teal-hover-strong, 제목·설명 텍스트는
          --color-ink-charcoal / --color-stone-gray, 마스코트 안 자리표시 도형 radius는
          --radius-input(12px) 재사용.
        </p>

        <p className={styles.subheading}>추가 radius / shadow 토큰</p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--radius-onboarding-card</span><span>16px (step 3 선택 카드)</span></div>
          <div className={styles.specRow}><span>--shadow-onboarding-card</span><span>0 0 0 1.5px rgba(63,182,168,.4), 0 10px 26px -18px rgba(21,50,140,.35)</span></div>
          <div className={styles.specRow}><span>--shadow-onboarding-card-hover</span><span>0 0 0 1.5px rgba(63,182,168,.7), 0 14px 30px -16px rgba(21,50,140,.4)</span></div>
          <div className={styles.specRow}><span>--shadow-onboarding-cta</span><span>0 10px 20px -14px rgba(63,182,168,.7) ("다음" CTA 버튼)</span></div>
        </div>

        <p className={styles.subheading}>step 3 선택 카드</p>
        <div className={styles.componentCard}>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <button type="button" className={styles.onboardingChoiceCard}>
                <span className={styles.onboardingChoiceCardTitle}>사업 아이디어를 구상하고 싶어요</span>
                <span className={styles.onboardingChoiceCardDesc}>
                  짧은 질문 혹은 정밀 질문에 답하며 사업을 구체화해요
                </span>
              </button>
              <span className={styles.codeLabel}>
                Card · --radius-onboarding-card · --shadow-onboarding-card / -hover
              </span>
            </div>
          </div>
          <div className={styles.componentRow}>
            <div className={styles.componentItem}>
              <div className={styles.onboardingDots}>
                <span className={`${styles.onboardingDot} ${styles.onboardingDotActive}`} />
                <span className={styles.onboardingDot} />
                <span className={styles.onboardingDot} />
                <span className={styles.onboardingDot} />
              </div>
              <span className={styles.codeLabel}>
                페이지 인디케이터 · 현재 22×6 --color-deep-navy / 나머지 6×6 --color-dot-inactive
              </span>
            </div>
            <div className={styles.componentItem}>
              <button type="button" className={styles.onboardingCta}>다음</button>
              <span className={styles.codeLabel}>CTA · 높이 46px · --radius-input · --shadow-onboarding-cta</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>12. 진단 방식 선택 (05-1)</h2>
        </div>

        <p className={styles.subheading}>추가 색상 토큰</p>
        <div className={styles.colorGrid}>
          {IDEACHOICE_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>
        <p className={styles.subheading}>
          카드 radius는 --radius-onboarding-card(16px), pill radius는 --radius-pill, "빠른 매칭"
          카드 그림자는 --shadow-onboarding-card / -hover, 텍스트·뱃지 색은 --color-ink-charcoal /
          --color-stone-gray / --color-teal-green / --color-deep-navy, "빠른 매칭" pill은
          --color-teal-mist + --color-teal-green, 헤더 워드마크 폰트는 --font-family-logo 재사용.
        </p>

        <p className={styles.subheading}>추가 shadow 토큰</p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--shadow-idea-card-navy</span><span>0 0 0 1.5px rgba(21,50,140,.4), 0 10px 26px -18px rgba(21,50,140,.35) ("정밀 구체화" 카드)</span></div>
          <div className={styles.specRow}><span>--shadow-idea-card-navy-hover</span><span>0 0 0 1.5px rgba(21,50,140,.7), 0 14px 30px -16px rgba(21,50,140,.4) ("정밀 구체화" 카드 hover)</span></div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>13. 사업구체화 질문 (06~10-4, isQ)</h2>
        </div>

        <p className={styles.subheading}>
          진행바 배경은 --color-dot-inactive, 채움은 --color-navy-sphere, 스텝뱃지는
          --color-stone-gray + --color-stone-mist, 토픽뱃지는 --color-teal-green +
          --color-teal-mist, 제목은 --color-ink-charcoal, 설명은 --color-stone-gray,
          textarea 배경은 --color-stone-mist(radius --radius-card), "다음" 버튼은
          --color-light-teal + hover --color-light-teal-hover-strong(radius --radius-cta),
          "이전" 버튼 테두리는 --shadow-inset-gray-strong 재사용.
        </p>

        <p className={styles.subheading}>추가 shadow 토큰</p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--shadow-inset-gray-strong-hover</span><span>inset 0 0 0 1.5px #8B8D93 ("이전" 버튼 hover)</span></div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>14. 사업구체화 리포트 요약 (13-1/14-2, is.reportASum/is.reportBSum)</h2>
        </div>

        <p className={styles.subheading}>추가 색상 토큰</p>
        <div className={styles.colorGrid}>
          {REPORTSUMMARY_COLORS.map((color) => (
            <div className={styles.colorCard} key={color.varName}>
              <div className={styles.swatch} style={{ backgroundColor: `var(${color.varName})` }} />
              <p className={styles.colorName}>{color.name}</p>
              <p className={styles.colorHex}>{color.hex}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
              <span className={styles.codeLabel}>{color.varName}</span>
            </div>
          ))}
        </div>
        <p className={styles.subheading}>
          서브헤더·CTA 배경은 --color-light-teal, "MULKKO REPORT" 텍스트·수익모델 아이콘 배경은
          --color-deep-navy, 보유역량 아이콘 배경은 --color-tab-active-icon, 라벨·설명·캡션 텍스트는
          --color-stone-gray, 헤딩은 --color-ink-charcoal 재사용.
        </p>

        <p className={styles.subheading}>추가 radius / shadow 토큰 (전부 재사용, 신규 없음)</p>
        <div className={styles.specList}>
          <div className={styles.specRow}><span>--shadow-inset-neutral</span><span>4축요약카드 테두리</span></div>
          <div className={styles.specRow}><span>--shadow-inset-report</span><span>"타깃 관점" 아이디어 카드 테두리</span></div>
          <div className={styles.specRow}><span>--shadow-inset-navy</span><span>"수익모델 관점" 아이디어 카드 테두리</span></div>
          <div className={styles.specRow}><span>--shadow-inset-amber</span><span>"보유역량 활용" 아이디어 카드 테두리</span></div>
          <div className={styles.specRow}><span>--shadow-inset-gray-strong</span><span>"이전" 버튼 테두리</span></div>
          <div className={styles.specRow}><span>--radius-card / --radius-cta / --radius-pill</span><span>아이디어 카드 14px / 하단 버튼 13px / 뱃지 99px</span></div>
        </div>
      </section>
    </div>
  );
}

export default WebStyleGuide;
