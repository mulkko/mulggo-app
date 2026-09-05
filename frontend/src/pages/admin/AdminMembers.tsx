import styles from "../../styles/adminMembers.module.css";

const STATS = [
  { label: "전체 회원", value: "1,284명", accent: false },
  { label: "오늘 신규", value: "+18명", accent: true },
  { label: "활성 (30일)", value: "742명", accent: false },
];

const MEMBERS = [
  { name: "김창업 님", email: "test1@mail.com", date: "2026.08.20", channel: "이메일 가입", type: "user" as const, status: "active" as const },
  { name: "㈜소상공플러스", email: "biz1@sosangplus.co.kr", date: "2026.08.19", channel: "카카오 가입", type: "biz" as const, status: "active" as const },
  { name: "박소상 님", email: "test3@mail.com", date: "2026.08.11", channel: "이메일 가입", type: "user" as const, status: "dormant" as const },
  { name: "㈜펫프렌즈", email: "contact@petfriends.kr", date: "2026.08.02", channel: "구글 가입", type: "biz" as const, status: "active" as const },
  { name: "정기술 님", email: "test5@mail.com", date: "2026.07.28", channel: "이메일 가입", type: "user" as const, status: "dormant" as const },
];

function UserIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c0-4 3.5-6 8-6s8 2 8 6" />
    </svg>
  );
}

function BuildingIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="4" y="3" width="16" height="18" rx="1" />
      <path d="M9 8h1M14 8h1M9 12h1M14 12h1M9 16h1M14 16h1" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg className={styles.searchIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </svg>
  );
}

function AdminMembers() {
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>회원 목록</h1>
      </div>

      <div className={styles.searchCard}>
        <div className={styles.searchInputWrap}>
          <SearchIcon />
          <input type="text" className={styles.searchInput} placeholder="이름, 이메일로 검색" />
        </div>
      </div>

      <div className={styles.statsRow}>
        {STATS.map((stat) => (
          <div className={styles.statCard} key={stat.label}>
            <p className={styles.statLabel}>{stat.label}</p>
            <p className={stat.accent ? styles.statValueAccent : styles.statValue}>{stat.value}</p>
          </div>
        ))}
      </div>

      <div className={styles.listCard}>
        <div className={styles.listHeader}>
          <p className={styles.listHeaderTitle}>가입 회원 리스트</p>
        </div>
        {MEMBERS.map((member) => (
          <div className={styles.memberRow} key={member.email}>
            <div className={styles.memberInfo}>
              <span className={styles.avatarCircle}>
                {member.type === "user" ? <UserIcon /> : <BuildingIcon />}
              </span>
              <div className={styles.memberText}>
                <div className={styles.nameRow}>
                  <p className={styles.memberName}>{member.name}</p>
                  <p className={styles.memberEmail}>({member.email})</p>
                </div>
                <p className={styles.memberMeta}>
                  가입 {member.date} · {member.channel}
                </p>
              </div>
            </div>
            <span className={`${styles.badge} ${member.status === "active" ? styles.badgeActive : styles.badgeDormant}`}>
              {member.status === "active" ? "활성" : "휴면"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default AdminMembers;
