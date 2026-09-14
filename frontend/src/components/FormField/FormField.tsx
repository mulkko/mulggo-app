import type { ChangeEvent } from "react";

/**
 * 공용 폼 필드 (라벨+인풋 / 라벨+select / select 화살표).
 *
 * [2026-09-14] ProfileEdit.tsx/ProfileEditV2.tsx/BizCertUpload.tsx가 각자 똑같은
 * TextField/SelectField/Chevron을 복사해서 갖고 있던 걸(MatchingList.tsx/
 * MatchingListDraft.tsx도 Chevron만 복사 - 그쪽은 지금 다른 세션이 작업 중이라
 * 이번 정리에서는 건드리지 않음) 하나로 합친 것 - 사용자 확인.
 *
 * CSS 모듈은 페이지마다 다른 파일(profileEdit.module.css 등)을 그대로 쓰므로,
 * 클래스 이름을 하드코딩하지 않고 호출하는 쪽의 styles 객체를 그대로 받아 쓴다
 * (.field/.label/.input/.inputInter/.inputReadonly/.selectWrap/.select 키가
 * 동일한 이름으로 존재해야 함 - 지금 대상 파일들은 전부 이미 이 이름 규칙을 따름).
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
  styles,
  label,
  name,
  value,
  options,
  onChange,
}: {
  styles: StyleMap;
  label: string;
  name: string;
  value: string;
  options: string[];
  onChange: (e: ChangeEvent<HTMLSelectElement>) => void;
}) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <div className={styles.selectWrap}>
        <select id={name} name={name} className={styles.select} value={value} onChange={onChange}>
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <Chevron className={styles.selectChevron} />
      </div>
    </div>
  );
}
