# 판정 UI 스프라이트

전투 판정 패널을 게임에서 조합해 사용할 수 있도록 네 개의 RGBA PNG로 분리했습니다. 파일에는 안내 문구와 움직이는 커서를 넣지 않았으므로 게임 코드에서 텍스트와 커서를 별도로 렌더링할 수 있습니다.

## 색상 의미
- `good_zone.png`: 청록색 GOOD 구간
- `perfect_zone.png`: 금빛 PERFECT 구간

## 권장 배치 (기준 디자인 단위)
- `panel_frame.png`: 판정 패널 바탕, 532×190
- `gauge_track.png`: 타이밍 레인 바탕, 400×22
- `good_zone.png`: GOOD 구간 오버레이, 136×22
- `perfect_zone.png`: 중앙 PERFECT 구간 오버레이, 44×22
- 커서: 현재 판정 진행도에 맞춰 코드에서 그리기

패널 → 레인 바탕 → GOOD 구간 → PERFECT 구간 → 동적 커서 순서로 겹쳐 그리면 됩니다. PNG는 각 권장 표시 크기의 2배 해상도입니다.
