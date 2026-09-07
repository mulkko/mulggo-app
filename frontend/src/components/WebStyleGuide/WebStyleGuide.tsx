import styles from "./WebStyleGuide.module.css";

const COLORS = [
  { name: "Navy Sphere", hex: "#104A8F", usage: "CTA 버튼 후보 (★검토중)", varName: "--color-navy-sphere" },
  { name: "Aqua Teal", hex: "#3FB6A8", usage: "메인 버튼·입력 테두리", varName: "--color-aqua-teal" },
  { name: "Amber Mist", hex: "#FFF3D6", usage: "라이트 배지 배경", varName: "--color-amber-mist" },
  { name: "Teal Mist", hex: "#DFF3EF", usage: "슬롯필링 입력창·라이트 배지 배경", varName: "--color-teal-mist" },
  { name: "Cream", hex: "#FAF8F3", usage: "기본 배경", varName: "--color-cream" },
  { name: "Warm Amber", hex: "#E8A93C", usage: "D-day 배지·활성 탭 텍스트/아이콘 전용", varName: "--color-warm-amber" },
  { name: "Signal Yellow", hex: "#FFBC00", usage: "CTA 배경 전용 (다크 텍스트와 짝)", varName: "--color-signal-yellow" },
  { name: "Indigo Blue", hex: "#3753C1", usage: "보조 컬러 (★검토중)", varName: "--color-review-indigo-blue" },
  { name: "Royal Blue", hex: "#3B57D4", usage: "보조 컬러 (★검토중)", varName: "--color-review-royal-blue" },
  { name: "Slate Blue", hex: "#5369CB", usage: "보조 컬러 (★검토중)", varName: "--color-review-slate-blue" },
  { name: "Ink Charcoal", hex: "#2E312E", usage: "본문 텍스트", varName: "--color-ink-charcoal" },
  { name: "Stone Gray", hex: "#8B8D93", usage: "보조 텍스트", varName: "--color-stone-gray" },
  { name: "Border Gray", hex: "#DCD8CC", usage: "보더 (PDF 미언급, 구조상 유지)", varName: "--color-border-web" },
  { name: "Error BG", hex: "#F2D1D1", usage: "에러 배지 배경 (PDF 미언급, 유지)", varName: "--color-error-bg-web" },
  { name: "Error Text", hex: "#C04040", usage: "에러 텍스트·보더 (PDF 미언급, 유지)", varName: "--color-error-text" },
  { name: "White", hex: "#FFFFFF", usage: "기본 페이지 배경", varName: "--color-white" },
  { name: "Amber Text", hex: "#8A6212", usage: "앰버 뱃지 텍스트 (판단 보류)", varName: "--color-amber-text" },
];

const LOGO_COLORS = [
  { name: "Logo Navy", hex: "#2A3286", varName: "--logo-navy" },
  { name: "Logo Mint", hex: "#ABE0D6", varName: "--logo-mint" },
];

const TYPOGRAPHY = [
  { tag: "TITLE", sizeLabel: "20–24px", weightLabel: "900", desc: "Display Title (Black)", sizeVar: "--font-size-title-max", weightVar: "--font-weight-title" },
  { tag: "HEADING", sizeLabel: "14–16px", weightLabel: "700", desc: "Section Header (Bold)", sizeVar: "--font-size-heading-max", weightVar: "--font-weight-heading" },
  { tag: "BODY", sizeLabel: "12.5–13.5px", weightLabel: "400–500", desc: "Primary Content", sizeVar: "--font-size-body-max", weightVar: "--font-weight-body-max" },
  { tag: "CAPTION", sizeLabel: "10.5–11.5px", weightLabel: "500", desc: "System & Muted (Stone Gray)", sizeVar: "--font-size-caption-max", weightVar: "--font-weight-caption" },
];

const NUMERIC_SAMPLE = { sizeLabel: "표·카드 수치 전용", weightLabel: "800 (Inter)" };

const BUTTONS = [
  { label: "다음 →", className: styles.btnNavy, code: ".btnNavy · Navy Sphere (★검토중)" },
  { label: "이전", className: styles.btnOutline, code: ".btnOutline" },
  { label: "전체보기 →", className: styles.btnTeal, code: ".btnTeal · Aqua Teal" },
  { label: "선택 불가", className: styles.btnDisabled, code: ".btnDisabled", disabled: true },
];

const BADGES = [
  { label: "마포구 기준", className: styles.pillTeal, code: ".pillTeal" },
  { label: "소상공인", className: styles.pillAmber, code: ".pillAmber" },
  { label: "오류", className: styles.pillError, code: ".pillError" },
];

function WebStyleGuide() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>MULKKO DESIGN SYSTEM</p>
        <h1 className={styles.title}>물꼬 스타일가이드 (Corporate)</h1>
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
          {TYPOGRAPHY.map((type) => (
            <div className={styles.typoRow} key={type.tag}>
              <span className={styles.typoTag}>{type.tag}</span>
              <p
                className={styles.typoPreview}
                style={{ fontSize: `var(${type.sizeVar})`, fontWeight: `var(${type.weightVar})` }}
              >
                다람쥐 헌 쳇바퀴에 타고파
              </p>
              <div className={styles.typoSpec}>
                <p className={styles.typoSpecDesc}>{type.desc}</p>
                <p className={styles.typoSpecValue}>{type.sizeLabel} / {type.weightLabel}</p>
              </div>
            </div>
          ))}
          <div className={styles.typoRow}>
            <span className={styles.typoTag}>NUMERIC</span>
            <p
              className={styles.typoPreview}
              style={{ fontFamily: "var(--font-family-numeric)", fontWeight: "var(--font-weight-numeric)" }}
            >
              1,234
            </p>
            <div className={styles.typoSpec}>
              <p className={styles.typoSpecDesc}>{NUMERIC_SAMPLE.sizeLabel}</p>
              <p className={styles.typoSpecValue}>{NUMERIC_SAMPLE.weightLabel}</p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className={styles.sectionTitleRow}>
          <span className={styles.sectionBar} />
          <h2 className={styles.sectionTitle}>03. INTERACTIVE COMPONENTS</h2>
        </div>
        <div className={styles.componentCard}>
          <div className={styles.componentRow}>
            {BUTTONS.map((btn) => (
              <div className={styles.componentItem} key={btn.code}>
                <button type="button" className={btn.className} disabled={btn.disabled}>
                  {btn.label}
                </button>
                <span className={styles.codeLabel}>{btn.code}</span>
              </div>
            ))}
          </div>
          <div className={styles.componentRow}>
            {BADGES.map((badge) => (
              <div className={styles.componentItem} key={badge.code}>
                <span className={badge.className}>{badge.label}</span>
                <span className={styles.codeLabel}>{badge.code}</span>
              </div>
            ))}
            <div className={styles.componentItem}>
              <div className={styles.inputPreview}>example@email.com</div>
              <span className={styles.codeLabel}>.inputPreview</span>
            </div>
            <div className={styles.componentItem}>
              <div className={styles.inputError}>invalid-email</div>
              <p className={styles.inputErrorHelp}>* 올바른 이메일 형식이 아닙니다</p>
              <span className={styles.codeLabel}>.inputError</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default WebStyleGuide;
