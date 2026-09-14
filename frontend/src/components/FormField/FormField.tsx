import type { ChangeEvent } from "react";
import SelectSheet from "../SelectSheet/SelectSheet";

/**
 * 공용 폼 필드 (라벨+인풋 / 라벨+select / select 화살표).
 *
 * [2026-09-14] ProfileEdit.tsx/ProfileEditV2.tsx/BizCertUpload.tsx/MatchingList.tsx/
 * MatchingListDraft.tsx가 각자 똑같은 TextField/SelectField/Chevron을 복사해서
 * 갖고 있던 걸 하나로 합친 것 - 사용자 확인.
 *
 * TextField/Chevron의 CSS 모듈은 페이지마다 다른 파일(profileEdit.module.css 등)을
 * 그대로 쓰므로, 클래스 이름을 하드코딩하지 않고 호출하는 쪽의 styles 객체를 그대로
 * 받아 쓴다 (.field/.label/.input/.inputInter/.inputReadonly 키가 동일한 이름으로
 * 존재해야 함).
 *
 * [2026-09-14] SelectField는 네이티브 <select> 대신 SelectSheet(하단 시트 팝업)로
 * 교체 - 브라우저/OS마다 네이티브 select 팝업 UI가 달라 디자인을 통일할 수 없다는
 * 문제(MatchingList.tsx가 이미 지역/업종/정렬 필터에서 이 이유로 SelectSheet를 씀)를
 * 이 5개 파일 전부에 한 번에 적용한 것(사용자 확인). SelectSheet는 자체 CSS를 쓰므로
 * styles prop은 안 쓰지만, 호출부(`<SelectField styles={styles} .../>`) 수정 없이
 * 그대로 컴파일되게 선택적(optional)으로 남겨둔다.
 */

type StyleMap = Record<string, string>;

export function Chevron({ className }: { className: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export function TextField({
  styles,
  label,
  name,
  value,
  onChange,
  inter = false,
  readOnly = false,
}: {
  styles: StyleMap;
  label: string;
  name: string;
  value: string;
  onChange?: (e: ChangeEvent<HTMLInputElement>) => void;
  inter?: boolean;
  readOnly?: boolean;
}) {
  const className = [
    styles.input,
    inter ? styles.inputInter : "",
    readOnly ? styles.inputReadonly : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <input
        id={name}
        name={name}
        className={className}
        value={value}
        onChange={onChange}
        readOnly={readOnly}
      />
    </div>
  );
}

export function SelectField({
  label,
  name,
  value,
  options,
  onChange,
}: {
  /** SelectSheet가 자체 CSS를 쓰므로 실제로는 안 읽지만, 기존 호출부
   * (`<SelectField styles={styles} .../>`)를 안 고쳐도 되게 받아만 둔다. */
  styles?: StyleMap;
  label: string;
  name: string;
  value: string;
  options: string[];
  onChange: (e: ChangeEvent<HTMLSelectElement>) => void;
}) {
  const sheetOptions = options.map((opt) => ({ label: opt, value: opt }));
  const handleSheetChange = (nextValue: string) => {
    onChange({ target: { name, value: nextValue } } as ChangeEvent<HTMLSelectElement>);
  };
  return (
    <SelectSheet
      label={label}
      name={name}
      value={value}
      options={sheetOptions}
      onChange={handleSheetChange}
    />
  );
}
