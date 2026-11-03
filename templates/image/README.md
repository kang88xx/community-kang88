# 이미지 템플릿 규약

- 파일: `templates/image/<name>.html` (Jinja2). Playwright가 뷰포트 크기로 스크린샷 → JPG.
- 템플릿은 `brand`(config/brand.yaml)와 `fields`(media_plan.json의 fields)만 참조한다.
- 같은 템플릿을 1600×900 / 1080×1080 / 1080×1350 뷰포트로 재렌더하므로 레이아웃은 **flex/grid + vw/vh 단위**로 작성.
- 각 템플릿 상단 주석에 `fields` 스펙을 적는다. Media Director 프롬프트에 이 목록이 그대로 들어간다.

초기 템플릿 세트(구현 단계에서 작성):
| 이름 | 용도 | fields |
|---|---|---|
| `announce_card` | 릴리즈/공지 | headline, subline, badge(선택), footer |
| `stat_card` | 숫자 1개 강조 | number, unit, label, context |
| `quote_card` | 인용/한 줄 메시지 | quote, author |
| `before_after` | 비교 | left_title, left_value, right_title, right_value, caption |
| `list_card` | 불릿 3~4개 | headline, items[] |
| `screenshot_frame` | 사용자 스크린샷을 기기 프레임/그라데이션 배경에 배치 | image, caption |
