import { NavLink, Outlet } from "react-router-dom";
import styles from "../../styles/adminLayout.module.css";
import adminLogo from "../../assets/admin/adminLogo.png";
import menuIcon01On from "../../assets/admin/menuIcon01_on.png";
import menuIcon01Off from "../../assets/admin/menuIcon01_off.png";
import menuIcon02On from "../../assets/admin/menuIcon02_on.png";
import menuIcon02Off from "../../assets/admin/menuIcon02_off.png";
import userPhoto from "../../assets/admin/userPhoto.png";

const MENU_ITEMS = [
  { to: "/admin", label: "공고 수집 현황", iconOn: menuIcon01On, iconOff: menuIcon01Off, end: true },
  { to: "/admin/members", label: "회원 관리", iconOn: menuIcon02On, iconOff: menuIcon02Off, end: false },
];

function AdminLayout() {
  return (
    <div className={styles.root}>
      <aside className={styles.sidebar}>
        <div className={styles.topGroup}>
          <div>
            <div className={styles.brandRow}>
              <img src={adminLogo} alt="" className={styles.iconCircle} />
              <p className={styles.brandTitle}>MULKKO 관리자</p>
            </div>
            <p className={styles.version}>System Admin v1.2.0</p>
          </div>
          <nav className={styles.menuRack}>
            {MENU_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive ? `${styles.menuItem} ${styles.menuItemActive}` : styles.menuItem
                }
              >
                {({ isActive }) => (
                  <>
                    <img src={isActive ? item.iconOn : item.iconOff} alt="" className={styles.menuIcon} />
                    {item.label}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className={styles.adminProfile}>
          <img src={userPhoto} alt="" className={styles.avatar} />
          <div>
            <p className={styles.profileName}>최최고 관리자</p>
            <p className={styles.profileRole}>Super Admin</p>
          </div>
        </div>
      </aside>

      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}

export default AdminLayout;
