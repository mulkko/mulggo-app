[작업 배경]
방금 추가한 마이페이지 헤더의 "1:1 문의" 마스코트 아이콘(`assets/8_white.png`, `.contactBtnImg`)이 너무 작아 보인다. 버튼 자리(`.contactBtn`, 28x28 원)는 그대로 두고, **안의 이미지 크기만 키워서** 캐릭터가 커 보이게 한다.

[수정 내용] (`styles/myPage.module.css`)
`.contactBtn` 자체(28x28, 배경 등)는 절대 건드리지 말고, `.contactBtnImg`의 width/height만 키워줘. `.contactBtn`에 `overflow: hidden`이 없다면(현재 없음) 이미지가 버튼 박스보다 커져도 잘리지 않고 그대로 더 크게 보임 — 그 상태를 이용하는 것.
```css
.contactBtnImg {
  width: 36px;
  height: 36px;
  object-fit: contain;
  display: block;
}
```
(24px → 36px으로. 이 값 기준으로 보고 여전히 작거나 너무 크면 32~40px 사이에서 미세 조정해도 됨.)

[작업 다 되면 알려줘]
이미지 커졌는지, 버튼 원 크기/위치는 그대로인지만 1줄로 알려줘.
