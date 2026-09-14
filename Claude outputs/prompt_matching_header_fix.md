[작업 배경]
`/matching`(`MatchingList.tsx`) 화면에서 딱 2가지만 고친다 — 상단 헤더의 "MULKKO MATCHING" 글씨체, 우측 로고. **그 외 이 화면의 다른 요소(필터바, 카드 리스트 등)와 기능은 전혀 건드리지 않는다.**

[원인 확인 — 참고만]
`.logoText`(`styles/matchingList.module.css`)의 `font-family: var(--font-family-logo)`(=`'Inter', sans-serif`)/weight 900/17px/`#15328C` 값 자체는 이미 프로토타입과 정확히 일치한다. 문제는 이 프로젝트에 Inter 폰트 파일을 실제로 불러오는 곳이 어디에도 없다는 것 — 그래서 이름만 Inter로 지정돼 있고 브라우저는 시스템 기본 폰트로 대체해서 보여주고 있었다(프로토타입 HTML은 Inter 웹폰트를 자체 내장하고 있어서 제대로 보였던 것). 로고는 `logoMark`가 실제 로고가 아니라 손으로 그린 물방울 모양 SVG placeholder였다 — 프로토타입엔 실제 물꼬 로고 이미지(28px 너비)가 들어가 있다(다른 화면들의 `logo.svg` import와 동일한 파일).

[레퍼런스]
프로토타입 파일: `docs/260912_2011_Mulkko Prototype (standalone).html`, grep 키 `is.match`(두 번째 등장, 15번 공고매칭리스트) — 헤더 로고 부분만 확인하면 충분, 이미 위에 값 다 있으니 다시 열어볼 필요 없음.

[수정 1 — Inter 폰트 실제 로드] (`frontend/index.html`)
`<head>` 안에 Google Fonts Inter 로드 추가(다른 화면들도 같이 정상화되는 부수효과 있음, 의도된 것):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
```
(정확한 위치는 기존 `<head>` 태그 안 아무 곳에나, `<title>` 근처에 추가하면 됨)

[수정 2 — 로고 이미지 교체] (`MatchingList.tsx`, `styles/matchingList.module.css`)
상단에 로고 import 추가(다른 화면들과 동일 패턴):
```
import logo from "../../assets/logo.svg";
```
`.logo` 안의 물방울 SVG(`<svg className={styles.logoMark} ...><path d="M12 3c3 3.6 6 6.9 6 10.5A6 6 0 0 1 6 13.5C6 9.9 9 6.6 12 3Z" /></svg>`)를 아래로 교체:
```
<img className={styles.logoMark} src={logo} alt="물꼬 로고" />
```
CSS `.logoMark`를 프로토타입 크기(28px 너비, 높이 auto)로 조정:
```
.logoMark {
  width: 28px;
  height: auto;
  display: block;
}
```

[작업 다 되면 알려줘]
폰트 로드 추가됐는지, 로고 이미지로 교체됐는지, 이 화면의 다른 부분/기능은 안 건드렸는지만 3줄 이내로 알려줘.
