[작업 배경]
`/mypage`(`MyPage.tsx`) 헤더에 원래 우측 상단에 "1:1 문의"(`/support`로 이동) 아이콘 버튼이 있었는데(`handleContactClick`/`.contactBtn`), 지금 코드를 보니 이 버튼의 JSX와 클릭 핸들러가 통째로 빠져있다(아마 이후 다른 작업 중 실수로 같이 지워진 것으로 보임 — CSS `.contactBtn`/`.contactBtn svg` 클래스는 `styles/myPage.module.css`에 그대로 남아있음, 28x28 버튼 자리). 이번엔 이걸 원래 위치(로고 반대편, 우측)에 되살리되, 아이콘을 기존 전화/헤드셋 모양 SVG 대신 **마스코트 이미지(`assets/8_white.png`)** 로 만든다.

**이 버튼 하나만 복구/교체한다 — 헤더의 로고나 다른 섹션(삭제 확인 팝업, 지원내역 등 최근에 작업한 것들)은 전혀 건드리지 않는다.**

[수정 내용] (`MyPage.tsx`)
1. 상단 import에 `import contactIcon from "../../assets/8_white.png";` 추가.
2. `handleProfileClick` 근처에 아래 핸들러 다시 추가:
```tsx
const handleContactClick = () => {
  navigate("/support");
};
```
3. 헤더를 아래처럼 복구(로고는 그대로 두고, 우측에 버튼만 추가 — `.header`는 이미 `justify-content: space-between`이라 로고 옆에 버튼만 넣으면 자동으로 양끝 배치됨):
```tsx
<header className={styles.header}>
  <span className={styles.logo}>
    <span className={styles.logoText}>MULKKO PAGE</span>
    <img src={logo} alt="물꼬 로고" className={styles.logoMark} />
  </span>
  <button
    type="button"
    className={styles.contactBtn}
    aria-label="1:1 문의"
    onClick={handleContactClick}
  >
    <img src={contactIcon} alt="" className={styles.contactBtnImg} />
  </button>
</header>
```
4. `styles/myPage.module.css`의 기존 `.contactBtn`(28x28, 배경 없음)은 그대로 두고, `.contactBtn svg` 규칙 대신(또는 추가로) 아래 클래스 추가:
```css
.contactBtnImg {
  width: 24px;
  height: 24px;
  object-fit: contain;
  display: block;
}
```
(직접 확인해보니 8_white 캐릭터는 헤드셋·이목구비·파란 받침대 색상 덕에 흰 배경 위에서도 윤곽이 잘 보여서, 별도 원형 배경 없이 아이콘만 올려도 잘 보임 — 혹시 너무 밋밋해 보이면 다른 화면들의 아바타 패턴처럼 `background: var(--color-teal-mist); border-radius:50%;`인 작은 원 안에 넣는 것도 방법이니, 이건 만들어보고 마음에 안 들면 알려줘도 됨.)

[작업 다 되면 알려줘]
1:1 문의 버튼이 우측 상단에 복구됐는지, 누르면 `/support`로 이동하는지, 아이콘이 마스코트 이미지로 잘 보이는지만 2~3줄로 알려줘.
