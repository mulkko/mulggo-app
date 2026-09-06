import styles from "./AdminStyleGuide.module.css";

const COLORS = [
  { name: "Primary Blue", hex: "#22B1F2", rgb: "RGB(34, 177, 242)", usage: "Primary Interaction", varName: "--color-primary-blue" },
  { name: "Brand Navy", hex: "#0F2B46", rgb: "RGB(15, 43, 70)", usage: "Deep Headers", varName: "--color-brand-navy" },
  { name: "Soft Accent Blue", hex: "#EAF6FF", rgb: "RGB(234, 246, 255)", usage: "Containers & Highlights", varName: "--color-soft-accent" },
  { name: "Success Green", hex: "#12B981", rgb: "RGB(18, 185, 129)", usage: "Success State", varName: "--color-success" },
  { name: "Warning Amber", hex: "#FEBC2E", rgb: "RGB(254, 188, 46)", usage: "Alert / Process", varName: "--color-warning" },
  { name: "Error Red", hex: "#EF4444", rgb: "RGB(239, 68, 68)", usage: "Danger / Failed", varName: "--color-error" },
  { name: "Dark Text", hex: "#1A1A1D", rgb: "RGB(26, 26, 29)", usage: "Primary Body", varName: "--color-text-dark" },
  { name: "Muted Gray", hex: "#6E6F76", rgb: "RGB(110, 111, 118)", usage: "Subtext & Borders", varName: "--color-text-muted" },
  { name: "Structural Border", hex: "#E3F0FA", rgb: "RGB(227, 240, 250)", usage: "Grid Lines", varName: "--color-border" },
];

const TYPOGRAPHY = [
  { tag: "H1", size: 28, weight: 900, lineHeight: 1.3, desc: "Header (Bold Display)", varName: "--font-size-h1" },
  { tag: "H2", size: 18, weight: 700, lineHeight: 1.4, desc: "Card Title (Semibold)", varName: "--font-size-h2" },
  { tag: "H3", size: 15, weight: 700, lineHeight: 1.4, desc: "Subheadings / Active List", varName: "--font-size-h3" },
  { tag: "BODY", size: 14, weight: 500, lineHeight: 1.5, desc: "Primary Content Text", varName: "--font-size-body" },
  { tag: "CAPTION", size: 11, weight: 500, lineHeight: 1.4, desc: "System Specs & Muted Logs", varName: "--font-size-caption" },
];

const BUTTONS = [
  { label: "확인 및 가입", className: "btnPrimary", code: ".btnPrimary" },
  { label: "이전 단계로", className: "btnSecondary", code: ".btnSecondary" },
  { label: "취소하기", className: "btnOutline", code: ".btnOutline" },
  { label: "선택 불가", className: "btnDisabled", code: ".btnDisabled", disabled: true },
];

const BADGES = [
  { label: "활성", className: "badgeSuccess", code: ".badgeSuccess" },
  { label: "휴면", className: "badgeMuted", code: ".badgeMuted" },
  { label: "실패", className: "badgeError", code: ".badgeError" },
];

function AdminStyleGuide() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <p className={styles.eyebrow}>MULKKO DESIGN SYSTEM</p>
        <h1 className={styles.title}>관리자 가이드 &amp; 스타일가이드 (Corporate)</h1>
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
              <p className={styles.colorRgb}>{color.rgb}</p>
              <p className={styles.colorUsage}>{color.usage}</p>
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
            <div className={styles.typoRow} key={type.varName}>
              <span className={styles.typoTag}>{type.tag}</span>
              <p
                className={styles.typoPreview}
                style={{ fontSize: `var(${type.varName})`, fontWeight: type.weight, lineHeight: type.lineHeight }}
              >
                다람쥐 헌 쳇바퀴에 타고파
              </p>
              <div className={styles.typoSpec}>
                <p className={styles.typoSpecDesc}>{type.desc}</p>
                <p className={styles.typoSpecValue}>
                  {type.size}px / {type.weight} / line-height {type.lineHeight}
                </p>
                <span className={styles.codeLabel}>{type.varName}</span>
              </div>
            </div>
          ))}
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
          </div>
        </div>
      </section>
    </div>
  );
}

export default AdminStyleGuide;
