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
    </div>
  );
}

export default WebStyleGuide;
