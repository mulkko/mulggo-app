[작업 배경]
FAB(문의하기 페이지 우측 하단 챗봇 버튼) 크기/테두리 문제 재수정. 지난 라운드에 적용한 "이미지 78~85%로 축소 + 흰 배경" 방식을 되돌리고, 원인부터 바로잡는다.

**원인 확인**: 지금 쓰는 `frontend/src/assets/8_white.svg`는 단순 아이콘이 아니라 **이미 자체적으로 원형 마스크가 적용된 300x300 캔버스 파일**(내부에 `<circle r="150">` clip mask + 이미지 위치 오프셋이 이미 들어있음)이다. 반면 같은 폴더의 `8_white.png`는 마스크 없는 600x600 정사각형 원본이다. 지금 컴포넌트가 이미 원형 마스크가 적용된 `.svg`를 가져다 쓰면서 `.fab`에서 `overflow:hidden; border-radius:50%`로 **또 한 번** 원형 클리핑을 하고 있어서, 원 안에 원이 겹치는 구조가 됐고 이게 작게(56px) 렌더링될 때 가장자리에 얇은 선처럼 보이는 테두리 아티팩트의 원인으로 추정된다. 해상도 문제는 아님(둘 다 원본 해상도 충분).

[수정 내용]
`CustomerSupport.tsx`의 import를 `8_white.svg` → **`8_white.png`**로 교체:
```
import fabIcon from "../../assets/8_white.png";
```

`.fab`/`.fabImg`(`customerSupport.module.css`)를 아래로 정리 — 지난번에 추가한 축소(78~85%) 관련 스타일은 전부 제거하고 단순하게:
```
.fab {
  position: absolute;
  right: 16px;
  bottom: 24px;
  width: 56px;
  height: 56px;
  border: none;
  border-radius: 50%;
  overflow: hidden;
  padding: 0;
  cursor: pointer;
  background: #FFFFFF;
  box-shadow: 0 10px 24px -6px rgba(21,50,140,.45), 0 4px 10px -2px rgba(21,50,140,.3);
  z-index: 10;
}

.fabImg {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
```
(원형 클리핑은 `.fab`의 `border-radius:50%; overflow:hidden` 이 한 곳에서만 하고, 이미지 자체엔 별도 마스크/축소 없이 100% 그대로 채움 — 이게 원래 사용자가 마음에 들어했던 크기/해상도 버전과 같은 방식.)

로컬 개발서버(`http://localhost:5173/support`)에서 렌더링 확인해서, 이전에 "테두리처럼 보였던" 선이 사라졌는지, 크기가 원래(축소하기 전) 버전만큼 커 보이는지 확인. 혹시 캐릭터 하관/이마 쪽이 원 밖으로 살짝 잘려 아쉬우면, 이미지 크기를 줄이지 말고 `object-position`(예: `center 40%` 등)으로 살짝 위/아래로 이동해서 잘리는 부분만 조정 — 전체 크기를 다시 줄이지는 말 것.

[작업 다 되면 알려줘]
png로 교체됐는지, 테두리 아티팩트 사라졌는지, 크기가 축소 전만큼 커졌는지만 2줄 이내로 알려줘.
