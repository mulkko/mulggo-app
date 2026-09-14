import { useState } from "react";
import styles from "./selectSheet.module.css";
import { Chevron } from "../FormField/FormField";

/**
 * 라벨 + "선택 시트" 필드 — 네이티브 <select> 대체 공통 컴포넌트.
 *
 * MatchingList.tsx가 지역/업종/정렬 필터에 쓰던 방식(칩 버튼 → 하단 시트 팝업의
 * 라디오 목록)과 같은 인터랙션이다. 네이티브 select는 브라우저/OS마다 팝업 UI가
 * 달라서 디자인을 통일할 수 없다는 게 그때 이유였는데(MatchingList.tsx 2026-09-10
 * 주석 참고), 폼 안의 select에도 같은 문제가 있어 이 컴포넌트로 뽑아냈다.
 * [2026-09-10] ProfileEdit.tsx(사업장 지역/대표자 연령대/기업유형)에서 처음 씀.
 *
 * 트리거 버튼 모양은 원래 네이티브 select가 있던 폼 필드 자리에 자연스럽게 붙도록
 * 인풋/select와 동일한 배경·높이를 쓰고, 팝업(시트)만 MatchingList와 동일 스펙이다.
 *
 * [2026-09-14] variant="chip" 추가 - MatchingList.tsx가 지역/업종/정렬 필터칩에
 * 쓰던 것도 사실 이 컴포넌트를 안 쓰고 시트 팝업 부분을 통째로 복제하고 있었다
 * (사용자 확인, 정리 대상). 라벨+전체폭 트리거(field) 대신 라벨 없는 작은 칩
 * 트리거만 그리고, 시트 팝업 부분은 두 variant가 완전히 동일한 코드를 공유한다.
 * chip은 화면마다 칩 모양이 달라서(예: MatchingList의 균등폭 flex 배치) 시각 스타일을
 * 이 컴포넌트가 강제하지 않고 호출부가 className으로 전부 넘겨준다.
 */

export interface SelectSheetOption {
  label: string;
  value: string;
}

interface SelectSheetProps {
  label: string;
  name: string;
  value: string;
  options: SelectSheetOption[];
  onChange: (value: string) => void;
  /** value가 빈 문자열이거나 아직 options에 없을 때 트리거에 보여줄 문구. 기본값: label. */
  placeholder?: string;
  /** true면 트리거를 눌러도 시트가 안 열림(상위 선택 전이라 옵션이 없는 경우 등). */
  disabled?: boolean;
  /** "field"(기본값): 라벨+전체폭 트리거(폼용). "chip": 라벨 없는 작은 칩 트리거만(필터바용). */
  variant?: "field" | "chip";
  /** variant="chip"일 때 트리거 버튼에 얹을 호출부 스타일(배경·패딩·flex 배치 등 전부 이걸로). */
  className?: string;
}

function SelectSheet({
  label,
  name,
  value,
  options,
  onChange,
  placeholder,
  disabled = false,
  variant = "field",
  className,
}: SelectSheetProps) {
  const [open, setOpen] = useState(false);
  const selectedLabel = options.find((o) => o.value === value)?.label ?? placeholder ?? label;

  const trigger =
    variant === "chip" ? (
      <button
        type="button"
        className={className}
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-label={label}
        disabled={disabled}
      >
        <span className={styles.chipTriggerLabel}>{selectedLabel}</span>
        <Chevron className={styles.chipChevron} />
      </button>
    ) : (
      <div className={styles.field}>
        <span className={styles.label} id={`${name}-label`}>
          {label}
        </span>
        <button
          type="button"
          className={styles.trigger}
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-labelledby={`${name}-label`}
          disabled={disabled}
        >
          {selectedLabel}
          <Chevron className={styles.chevron} />
        </button>
      </div>
    );

  return (
    <>
      {trigger}

      {open && (
        <div className={styles.sheetOverlay} onClick={() => setOpen(false)}>
          <div
            className={styles.sheetPanel}
            role="dialog"
            aria-modal="true"
            aria-label={label}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.sheetHead}>
              <span className={styles.sheetTitle}>{label}</span>
              <button
                type="button"
                className={styles.sheetCloseBtn}
                aria-label="닫기"
                onClick={() => setOpen(false)}
              >
                ✕
              </button>
            </div>
            <ul className={styles.sheetList}>
              {options.map((opt) => {
                const active = opt.value === value;
                return (
                  <li key={opt.value}>
                    <button
                      type="button"
                      className={styles.sheetOption}
                      onClick={() => {
                        onChange(opt.value);
                        setOpen(false);
                      }}
                    >
                      <span className={`${styles.radio} ${active ? styles.radioOn : ""}`} aria-hidden="true" />
                      <span>{opt.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}

export default SelectSheet;
