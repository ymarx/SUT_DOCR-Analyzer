# DrawingRecord dataclass 설명 

워드 문서(.docx)에서 추출된 drawings 데이터에서 다이어그램 생성 시 도움이 될 수 있는 요소를 최소한으로 전처리하였습니다.  
\
bbox가 없어도 xml_snippet의 정보를 활용해 도형들을 다이어그램(예: 순서도)으로 묶을 수 있습니다.  


## `drawings_raw`란?

`drawings_raw`는 워드 문서의 도형(예: 사각형, 화살표, 텍스트 박스) 정보를 담은 딕셔너리 리스트입니다. 예시(간략화):

```json
{
  "did": "d0",  // 고유 ID
  "kind": "shape",  // 객체 종류
  "texts_raw": [{"text": "②통기성 확보", "xpath": ".//w:t"}],  // 텍스트 정보
  "image": null,  // 이미지 여부
  "shape": {
    "preset": "rect",  // 도형 종류(사각형, 화살표 등)
    "texts_raw": [...],
    "tag": "..."
  },
  "group": null,  // 그룹 정보(기본 null)
  "bbox": null,  // 좌표(종종 null)
  "page": null,  // 페이지 정보(종종 null)
  "xml_snippet": "<ns0:drawing ...>"  // OpenXML 원문
}
```

다이어그램을 그룹화하려면 xml_snippet에서 다음 필드를 추출해 "의사-좌표" 특징을 만듭니다.

## 주요 필드

### `Position Offsets (x_rel, y_rel)`

위치: <wp:positionH/wp:posOffset> (x), <wp:positionV/wp:posOffset> (y)  
설명: 문단/열 기준 상대 위치(EMU 단위, 1 EMU ≈ 1/914400인치). 절대 좌표는 아니지만 도형 간 "가까움" 판단에 사용.  
예: x_rel=1769607, y_rel=254856


### `Extent` (w_rel, h_rel)

위치: <wp:extent cx=... cy=...>   
설명: 도형의 너비(cx)와 높이(cy). 크기 비교로 비슷한 도형 식별.   
예: cx=1160891, cy=349857   


### `Z-Order` (z)

위치: <wp:anchor relativeHeight=...>   
설명: 도형의 쌓임 순서. Z 값이 비슷하면 같은 다이어그램일 가능성 높음.   
예: relativeHeight=251661312   


### `Context` (p_idx, tc_sig)

`p_idx`: 문서에서 도형이 속한 문단(<w:p>)의 인덱스.  
`tc_sig`: 표 셀(<w:tc>) 식별자(예: "row:col:tableIndex"). 없으면 None.  
설명: 같은 문단/셀 내 도형은 같은 다이어그램일 가능성 높음.  


### `Shape Type` (preset)

위치: `shape.preset` (예: "rect", "rightArrow")    
설명: 화살표류(rightArrow 등)는 커넥터로, 다른 도형을 연결.     


### `Wrapping` (wrap)

위치: <wp:wrapNone/>, <wp:wrapSquare/> 등  
설명: 배치 방식. 같은 방식은 같은 다이어그램일 가능성. 


### `Text Signature` (text_sig)

위치: texts_raw.text  
설명: 텍스트 패턴(예: "②")으로 순서/관련성 파악.  



## 2. 그룹화 규칙

### 강한 규칙 (즉시 같은 다이어그램으로 묶음):

같은 tc_sig (같은 표 셀).  
같은 p_idx이고 |x_rel| + |y_rel| 차이가 작음 (예: < 300,000 EMU).  

  
### 약한 규칙 (가까운 후보):

p_idx 차이 ≤ 2, y_rel 차이 < 500,000 EMU.  
x_rel 차이 < 600,000 EMU, 크기 비율(w_rel/h_rel) 0.6~1.4.  
  
  
### 커넥터 연결:
preset이 화살표면, 가장 가까운 두 도형을 찾아 그룹 합침.  