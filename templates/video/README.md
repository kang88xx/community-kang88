# 비디오/GIF 템플릿 규약

- GIF: 이미지 템플릿 프레임 2~5장을 `seconds_per_frame` 간격으로 이어붙임(크로스페이드 0.3s). ffmpeg palettegen/paletteuse. 용량 초과 시 fps(15→10) → 가로폭(800→640→480) 순으로 자동 축소.
- MP4: `scenes[]` 각각이 이미지 템플릿 또는 asset 구간. Ken Burns(1.0→1.08 줌) 기본 적용, 자막은 ASS로 번인. 코덱 H.264 yuv420p + AAC, `-movflags +faststart`.
- 모든 GIF는 MP4 쌍둥이를 함께 출력(Telegram/X/LinkedIn 모두 MP4 처리가 더 안정적).
