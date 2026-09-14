import styles from "../../styles/announcementCard.module.css";

/**
 * 지원사업(공고) 카드 — 공통 컴포넌트.
 *
 * 공고 매칭 리스트(MatchingList)와 마이페이지의 "관심있는 지원사업" 섹션이
 * 같은 카드를 쓰기 때문에 별도 컴포넌트로 분리했다.
 *
 * - 카드 본문 클릭: `onClick` (보통 공고 상세로 이동)
 * - `onDelete`를 넘기면 우측 상단에 삭제(X) 버튼이 나타난다. (마이페이지 전용)
 *   삭제 버튼 클릭은 본문 클릭으로 전파되지 않는다.
 */

interface AnnouncementCardData {
  id: string;
  /** 주관 기관명 */
  agency: string;
  /** 마감 임박도 뱃지 문구 (예: "모집중 D-6") */
  dday: string;
  /** 공고 제목 */
  title: string;
  /** 해시태그 (보통 2개 - 로직 확정 전까지는 개수 유동적) */
  tags: string[];
  /** [임시] 채우기 가능한 서류가 있는 공고인지 (backend/api/matching.py fillable) */
  fillable?: boolean;
  /** [임시] 매칭된 KSIC 업종코드 확인용 (backend/api/matching.py ksicCodesMatched) */
  ksicCodesMatched?: string[];
}

interface AnnouncementCardProps {
  item: AnnouncementCardData;
  /** 카드 본문 클릭 핸들러 */
  onClick?: (item: AnnouncementCardData) => void;
  /** 넘기면 우측 상단 삭제(X) 버튼이 표시된다. */
  onDelete?: (id: string) => void;
}

function AnnouncementCard({ item, onClick, onDelete }: AnnouncementCardProps) {
  return (
    <div className={styles.card}>
      <button
        type="button"
        className={styles.body}
        onClick={onClick ? () => onClick(item) : undefined}
      >
        <div className={`${styles.top} ${onDelete ? styles.topWithDelete : ""}`}>
          <span className={styles.agencyGroup}>
            <span className={styles.agency}>{item.agency}</span>
          </span>
          <div className={styles.rightGroup}>
            {item.fillable && <span className={styles.fillableBadge}>채우기 가능</span>}
            <span className={styles.dday}>{item.dday}</span>
          </div>
        </div>
        <span className={styles.title}>{item.title}</span>
        <div className={styles.tagRow}>
          {item.tags.map((tag) => (
            <span key={tag} className={styles.tag}>
              {tag}
            </span>
          ))}
        </div>
      </button>

      {onDelete && (
        <button
          type="button"
          className={styles.deleteBtn}
          aria-label="목록에서 삭제"
          onClick={() => onDelete(item.id)}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            aria-hidden="true"
          >
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      )}
    </div>
  );
}

export default AnnouncementCard;
export type { AnnouncementCardData };
