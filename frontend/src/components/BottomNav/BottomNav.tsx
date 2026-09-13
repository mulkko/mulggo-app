import { useNavigate } from "react-router-dom";
import styles from "../../styles/bottomNav.module.css";

/**
 * 앱 하단 고정 네비게이션 (공통 컴포넌트).
 *
 * 사용자(web) 화면 어디서든 재사용한다. 현재 화면이 어떤 탭에 해당하는지는
 * `active` prop으로 넘긴다.
 *
 * [2026-09-09] 홈/매칭/마이페이지는 App.tsx에 라우트가 이미 있어서 이동 연결함.
 * [2026-09-13, 사용자 확인] "아이디어" 탭은 진단하기 메인(/diagnosis/choice, 진단 방식
 * 선택 화면)으로 연결 - 더 이상 미연결 TODO 아님.
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
    path: "/diagnosis/choice",
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
    if (tab.key === active) return;
    navigate(tab.path);
  };

  return (
    <>
      {/* [2026-09-13, 사용자 확인] .nav가 position:fixed라 문서 흐름에서 빠진다 -
          이 스페이서가 같은 높이(74px)만큼 자리를 대신 차지해서, 이 컴포넌트를 쓰는
          화면의 실제 콘텐츠(버튼 등)가 고정된 nav에 가려지지 않게 한다. */}
      <div className={styles.navSpacer} aria-hidden="true" />
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
    </>
  );
}

export default BottomNav;
export type { TabKey };
