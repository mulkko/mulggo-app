import { useNavigate } from "react-router-dom";
import styles from "../../styles/bottomNav.module.css";

/**
 * 앱 하단 고정 네비게이션 (공통 컴포넌트).
 *
 * 사용자(web) 화면 어디서든 재사용한다. 현재 화면이 어떤 탭에 해당하는지는
 * `active` prop으로 넘긴다.
 *
 * [2026-09-09] 홈/매칭/마이페이지는 App.tsx에 라우트가 이미 있어서 이동 연결함.
 * "아이디어" 탭(/idea)은 아직 라우트 자체가 없어서(사업구체화 챗봇 화면 미정)
 * 클릭해도 이동 안 시키고 TODO로 남겨둠 - 그 화면 라우트 확정되면 연결.
 *
 * 사용 예:
 *   <BottomNav active="matching" />
 */

type TabKey = "home" | "idea" | "matching" | "my";

interface BottomNavProps {
  /** 현재 화면에 해당하는 탭. 이 탭만 활성 스타일로 표시된다. */
  active: TabKey;
}

interface TabDef {
  key: TabKey;
  label: string;
  /** 이동할 라우트 경로 (라우팅 연결 전까지는 참고용) */
  path: string;
  /** 24x24 viewBox 기준 아이콘 path(들) */
  icon: React.ReactNode;
}

const TABS: TabDef[] = [
  {
    key: "home",
    label: "홈",
    path: "/home",
    icon: (
      <>
        <path d="M4 11 12 4l8 7" />
        <path d="M6.5 9.6V20h11V9.6" />
      </>
    ),
  },
  {
    key: "idea",
    label: "아이디어",
    path: "/idea",
    icon: (
      <>
        <path d="M9.5 18h5" />
        <path d="M10.5 21h3" />
        <path d="M12 3.5a5.6 5.6 0 0 0-3.3 10.2V15h6.6v-1.3A5.6 5.6 0 0 0 12 3.5Z" />
      </>
    ),
  },
  {
    key: "matching",
    label: "매칭",
    path: "/matching",
    icon: (
      <>
        <path d="M6.5 3.5h8L18 7v13.5H6.5Z" />
        <path d="M9.5 11h5M9.5 15h5" />
      </>
    ),
  },
  {
    key: "my",
    label: "마이페이지",
    path: "/mypage",
    icon: (
      <>
        <circle cx="12" cy="8.4" r="3.6" />
        <path d="M5.5 20c1.1-3.4 3.6-5 6.5-5s5.4 1.6 6.5 5" />
      </>
    ),
  },
];

function BottomNav({ active }: BottomNavProps) {
  const navigate = useNavigate();

  const handleTabClick = (tab: TabDef) => {
    if (tab.key === "idea") return; // TODO: /idea 라우트 생기면 이동 연결
    if (tab.key === active) return;
    navigate(tab.path);
  };

  return (
    <nav className={styles.nav} aria-label="주요 메뉴">
      {TABS.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            type="button"
            className={styles.tab}
            aria-current={isActive ? "page" : undefined}
            onClick={() => handleTabClick(tab)}
          >
            <svg
              className={`${styles.icon} ${isActive ? styles.iconActive : ""}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              {tab.icon}
            </svg>
            <span className={`${styles.label} ${isActive ? styles.labelActive : ""}`}>
              {tab.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

export default BottomNav;
export type { TabKey };
