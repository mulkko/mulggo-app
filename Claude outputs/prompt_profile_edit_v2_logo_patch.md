[작업 배경]
지난 라운드에 만든 `pages/mypage/ProfileEditV2.tsx`(라우트 `/edit-v2`)에서 상단 프로필 사진 자리(`.avatarBlock` 안 `.avatar`)에 지금 사람 실루엣 아이콘(SVG, circle+path)이 들어가 있는데, 프로토타입은 이 자리에 실제 물꼬 로고(파도+물방울 마크)를 넣어둔 것으로 확인됨. 이 부분만 교체한다 — 다른 항목/레이아웃/기능은 전혀 건드리지 않음.

[레퍼런스]
프로토타입 파일: `docs/260912_2011_Mulkko Prototype (standalone).html`, grep 키 `is.profile`(두 번째 등장) — 프로필 사진 자리의 `<img>`가 가리키는 실제 이미지를 디코딩해서 확인한 결과, 물꼬 브랜드 로고(파도+물방울, 다른 화면들에서 이미 쓰는 것과 동일한 이미지)였음. 이미 `Splash.tsx` 등 다른 화면에서 `import logo from '../../assets/logo.svg'` (또는 `.png`, 결과 동일) 방식으로 쓰고 있으니 그 컨벤션 그대로 따르면 됨 — 새로 프로토타입 파일 열어볼 필요 없음.

[수정 내용]
`ProfileEditV2.tsx` 상단에 로고 import 추가(다른 화면과 동일 패턴):
```
import logo from "../../assets/logo.svg";
```

`.avatar` 안의 사람 실루엣 SVG(`<svg>...<circle cx="12" cy="8" r="4" /><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7" /></svg>`)를 아래로 교체:
```
<img src={logo} alt="물꼬 로고" style={{ width: 46, height: "auto", display: "block" }} />
```

CSS(`styles/profileEditV2.module.css`)의 `.avatar svg`(46x46, display:block) 규칙은 이제 안 쓰니 지워도 되고, 필요하면 `.avatar img`로 이름만 바꿔서 유지해도 됨(`width:46px; height:auto; display:block;`). `.avatar`의 배경(`var(--color-teal-mist)`)·원형 크기(76x76)는 그대로 유지.

[작업 다 되면 알려줘]
로고 이미지로 교체됐는지, 다른 부분은 안 건드렸는지만 2줄 이내로 알려줘.
