---
title: "v2.0 릴리즈 — 실시간 협업 기능"
slug: v2-release                 # output 폴더명에 사용
goal: announce                   # announce | educate | engage | recruit | promote
audience: "개발자, 얼리어답터, 소규모 팀 리드"
tone: "친근하지만 전문적. 과장 금지, 숫자로 말하기"
language:
  default: [ko]
  reddit: [en]
  linkedin: [en]
  x: [en]
cta: "GitHub에서 ⭐ 누르고 베타 신청"
links:
  - label: 릴리즈 노트
    url: https://example.com/release
  - label: GitHub
    url: https://github.com/example/repo
assets:
  - path: assets/stock/dashboard.png
    caption: "새 협업 대시보드 스크린샷"
  - path: assets/stock/demo.mp4
    caption: "실시간 커서 공유 10초 데모"
media:
  default: [jpg]
  x: [jpg, gif]
  telegram: [jpg, mp4]
  linkedin: [jpg_portrait]
platforms: [telegram, x, reddit, linkedin]   # 하나만 적으면 단독 모드 (예: [x])
reddit:
  subreddits: [r/webdev, r/SideProject]
  post_type: text               # text | image | video
---

## 핵심 내용
- 실시간 커서·선택 영역 공유 (최대 50명 동시)
- 동기화 지연 50ms → 12ms (CRDT 엔진 교체)
- 오프라인 편집 후 자동 머지
- 베타 기간 무료, 11월 말까지

## 배경 / 스토리
6개월간 가장 많이 들어온 요청이 "같이 편집하기"였다. ...

## 피해야 할 표현
- "혁명적", "업계 최초", "게임 체인저"
- 경쟁사 직접 언급

## 플랫폼별 메모 (선택)
- reddit: 홍보 느낌 빼고 CRDT 전환 과정의 기술적 교훈 중심으로
- linkedin: 팀 리드 관점의 생산성 효과 강조
