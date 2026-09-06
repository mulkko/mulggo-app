import { useEffect, useMemo, useState } from "react";
import styles from "../../styles/adminMembers.module.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

interface Member {
  user_id: number;
  name: string;
  email: string;
  created_at: string;
  applicant_type: string | null;
  last_login_at: string | null;
  status: "active" | "dormant";
}

interface MembersResponse {
  success: boolean;
  data: {
    members: Member[];
    stats: { total: number; new_today: number; active_30d: number };
  } | null;
}

function formatDateKST(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).replace(/\. /g, ".").replace(/\.$/, "");
}

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
  const [members, setMembers] = useState<Member[]>([]);
  const [stats, setStats] = useState({ total: 0, new_today: 0, active_30d: 0 });
  const [search, setSearch] = useState("");
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE_URL}/admin/members`)
      .then((res) => res.json())
      .then((res: MembersResponse) => {
        if (res.success && res.data) {
          setMembers(res.data.members);
          setStats(res.data.stats);
        } else {
          setLoadError(true);
        }
      })
      .catch(() => setLoadError(true));
  }, []);

  const filteredMembers = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return members;
    return members.filter(
      (m) => m.name.toLowerCase().includes(q) || m.email.toLowerCase().includes(q)
    );
  }, [members, search]);

  const STATS = [
    { label: "전체 회원", value: `${stats.total.toLocaleString()}명`, accent: false },
    { label: "오늘 신규", value: `+${stats.new_today.toLocaleString()}명`, accent: true },
    { label: "활성 (30일)", value: `${stats.active_30d.toLocaleString()}명`, accent: false },
  ];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.pageTitle}>회원 목록</h1>
      </div>

      <div className={styles.searchCard}>
        <div className={styles.searchInputWrap}>
          <SearchIcon />
          <input
            type="text"
            className={styles.searchInput}
            placeholder="이름, 이메일로 검색"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
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

        {loadError && <p>회원 목록을 불러오지 못했습니다.</p>}

        {filteredMembers.map((member) => (
          <div className={styles.memberRow} key={member.user_id}>
            <div className={styles.memberInfo}>
              <span className={styles.avatarCircle}>
                {member.applicant_type === "corporate" ? <BuildingIcon /> : <UserIcon />}
              </span>
              <div className={styles.memberText}>
                <div className={styles.nameRow}>
                  <p className={styles.memberName}>{member.name} 님</p>
                  <p className={styles.memberEmail}>({member.email})</p>
                </div>
                <p className={styles.memberMeta}>
                  가입 {formatDateKST(member.created_at)} · 이메일 가입
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
