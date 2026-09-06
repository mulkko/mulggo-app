import { useNavigate } from "react-router-dom";
import styles from '../../styles/splash.module.css'; // 객체 형태로 불러옴
import logo from '../../assets/logo.svg';

function Splash() {
  const navigate = useNavigate();

  // 화면을 탭하면 로그인 화면으로 이동한다.
  const handleTap = () => {
    navigate("/login");
  };

  return (
    <div className={styles.splashPage} onClick={handleTap}>
      <div className={styles.badge}>
        <img src={logo} alt="물꼬 로고" />
      </div>

      <div className={styles.textBox}>
        <h1 className={styles.title}>MULKKO</h1>
        <p className={styles.tagline}>창업의 물꼬를 트다</p>
      </div>

      <div className={styles.dots}>
        <span />
        <span />
        <span />
      </div>
      <p className={styles.hint}>화면을 탭하면 바로 이동해요</p>
    </div>
  );
}

export default Splash;
