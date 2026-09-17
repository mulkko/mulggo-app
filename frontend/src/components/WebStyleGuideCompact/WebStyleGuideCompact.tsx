// PPT/발표 자료용 축약 스타일가이드 - WebStyleGuideByFeature.tsx(개발자 참고용, 34개 색상
// 전부 + usage 설명)를 그대로 캡처하기엔 색상이 너무 많아 부담스럽다는 피드백(2026-09-16)
// 으로 별도 페이지를 새로 만들었다. 계열(네이비/틸그린/그레이/포인트)당 대표색 3~4개만,
// 이름+HEX만 보여주고 usage 설명·코드 변수명은 뺐다 - 한 화면(스크롤 없이)에 다 들어가게
// 색상+타이포 핵심만 담아 캡처 한 장으로 쓰기 좋게 구성.
import styles from "./webStyleGuideCompact.module.css";

interface CompactColor {
  name: string;
  hex: string;
}

interface CompactGroup {
  label: string;
  colors: CompactColor[];
}

const COLOR_GROUPS: CompactGroup[] = [
  {
    label: "Navy",
    colors: [
      { name: "Navy Sphere", hex: "#104A8F" },
      { name: "Deep Navy", hex: "#15328C" },
      { name: "Navy Mist", hex: "#E7ECF8" },
    ],
  },
  {
    label: "Teal · Green",
    colors: [
      { name: "Teal Green", hex: "#0F6E62" },
      { name: "Light Teal", hex: "#3FB6A8" },
      { name: "Teal Mist", hex: "#DFF3EF" },
    ],
  },
  {
    label: "Gray · Neutral",
    colors: [
      { name: "Ink Charcoal", hex: "#2E312E" },
      { name: "Stone Gray", hex: "#8B8D93" },
      { name: "Stone Mist", hex: "#EFEFF1" },
      { name: "White", hex: "#FFFFFF" },
    ],
  },
  {
    label: "Point Color",
    colors: [
      { name: "Gold", hex: "#E8A93C" },
      { name: "Purple Accent", hex: "#7C5CBF" },
      { name: "Danger", hex: "#E0273F" },
    ],
  },
];

const TYPE_SAMPLES = [
  { tag: "LOGO", sample: "MULKKO", spec: "32px · 900" },
  { tag: "H1", sample: "화면 타이틀", spec: "16px · 700" },
  { tag: "BODY", sample: "본문/값 텍스트", spec: "14px · 400" },
  { tag: "CAPTION", sample: "캡션/보조 텍스트", spec: "11px · 400" },
];

function WebStyleGuideCompact() {
  return (
    <div className={styles.page}>
      <p className={styles.eyebrow}>MULKKO DESIGN SYSTEM</p>
      <h1 className={styles.title}>Color &amp; Typography</h1>

      <div className={styles.colorGroups}>
        {COLOR_GROUPS.map((group) => (
          <div className={styles.group} key={group.label}>
            <p className={styles.groupLabel}>{group.label}</p>
            <div className={styles.swatchRow}>
              {group.colors.map((color) => (
                <div className={styles.swatchCard} key={color.hex}>
                  <div className={styles.swatch} style={{ backgroundColor: color.hex }} />
                  <p className={styles.swatchName}>{color.name}</p>
                  <p className={styles.swatchHex}>{color.hex}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.typeRow}>
        {TYPE_SAMPLES.map((t) => (
          <div className={styles.typeCard} key={t.tag}>
            <span className={styles.typeTag}>{t.tag}</span>
            <p className={styles.typeSample}>{t.sample}</p>
            <span className={styles.typeSpec}>{t.spec}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default WebStyleGuideCompact;
