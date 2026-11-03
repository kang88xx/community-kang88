# Community Post Agent — 설계 문서

> 목표: 하나의 브리프(주제/핵심 메시지/소스 자료)를 입력하면
> **Telegram / X / Reddit / LinkedIn** 4개 섹션별로 최적화된 **텍스트 + 미디어(JPG / GIF / MP4)** 를 생성해
> 사람이 검토·직접 업로드할 수 있는 패키지로 내보내는 에이전트.
>
> 1단계(현재): 생성 → 검토 패키지 출력. 자동 포스팅은 2단계에서 어댑터로 붙임.

---

## 1. 핵심 원칙

| 원칙 | 의미 |
|---|---|
| **플랫폼은 독립 섹션** | 네 플랫폼은 각각 독립적으로 실행 가능한 섹션. 한 브리프로 4개를 한 번에 만들 수도(캠페인), 플랫폼 하나만 따로 만들 수도(단독) 있음 |
| **같은 주제면 각색, 다른 주제면 분리** | 캠페인 모드에서는 같은 메시지를 플랫폼 문화·제약에 맞춰 *각색*. 단독 모드에서는 그 플랫폼만의 주제로 독립 생성 |
| **LLM은 글/컨셉, 코드는 검증/렌더링** | 글자 수·해시태그 수·파일 규격 같은 하드 제약은 LLM이 아닌 코드가 강제 |
| **검토 가능한 산출물** | 모든 결과는 파일로 남고, `REVIEW.md` 한 장에서 4개 플랫폼을 한눈에 비교 |
| **포스팅은 플러그인** | 1단계 산출물(`post.json` + 미디어)이 2단계 포스터의 입력 계약이 됨 |

---

## 2. 실행 모드

| 모드 | 언제 | 입력 | 출력 |
|---|---|---|---|
| **캠페인 (campaign)** | 같은 주제를 4개(또는 선택한 N개) 플랫폼에 한 번에 | 브리프 1개, `platforms: [telegram, x, reddit, linkedin]` | `output/<date>_<slug>/` 아래 플랫폼별 폴더 + 통합 `REVIEW.md` |
| **단독 (single)** | 플랫폼 하나만, 그 플랫폼 고유 주제로 | 브리프 1개, `platforms: [x]` 또는 CLI `--platform x` | `output/<date>_<slug>_x/` + 해당 플랫폼 `REVIEW.md` |
| **배치 (batch)** | 서로 다른 주제의 브리프 여러 개를 한 번에 | 폴더 또는 여러 파일 경로 | 브리프마다 위 둘 중 하나로 실행, 마지막에 `BATCH_SUMMARY.md` |

```bash
community run briefs/v2-release.md                      # 캠페인: 브리프의 platforms 전부
community run briefs/v2-release.md --platform x,reddit # 캠페인이지만 2개만
community run briefs/x-dev-tip-013.md                  # 단독: 브리프에 platforms: [x] 만 있음
community run briefs/*.md                               # 배치: 각 브리프를 독립 실행
```

모드에 따라 달라지는 것:
- **Planner**: 캠페인은 플랫폼별 앵글을 모두 뽑고 메시지 일관성을 잡음. 단독은 그 플랫폼 앵글만 뽑고 더 가볍게 돈다(effort `medium`).
- **Media Director**: 캠페인은 하나의 비주얼 컨셉을 플랫폼별 규격으로 변주. 단독은 그 플랫폼 규격만.
- **Reviewer**: `cross_platform` 일관성 검사는 플랫폼이 2개 이상일 때만.
- **출력 폴더명**: 단독은 슬러그 뒤에 플랫폼 접미사(`_x`, `_reddit`)가 붙어 같은 날 여러 단독 런이 섞이지 않음.

단독 모드용 브리프는 짧다. 예: X 전용 개발 팁 하나.
```yaml
---
title: "오늘의 팁: git worktree로 PR 리뷰 병렬화"
slug: x-dev-tip-013
platforms: [x]
goal: educate
media: {x: [jpg]}
---
- `git worktree add ../review-123 origin/pr-123` 한 줄로 ...
```

---

## 3. 전체 파이프라인

```
brief.md ──▶ ① Planner (LLM) ──▶ plan.json
                                  │
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                     ▼
   ② Writer ×4 (LLM, 병렬)   ③ Media Director (LLM)   (brand.yaml)
   telegram / x / reddit /    media_plan.json
   linkedin → post.json             │
            │                        ▼
            ▼                ④ Media Renderer (코드)
   ⑤ Validator (코드)         JPG / GIF / MP4
   규격 위반 → Writer 재호출          │
   (최대 2회, 에러 피드백 포함)         │
            └──────────┬─────────────┘
                       ▼
            ⑥ Reviewer (LLM, 선택)  → review.json (점수·수정 제안)
                       ▼
            ⑦ Packager (코드)       → output/<run_id>/ + REVIEW.md
```

### 단계별 책임

| # | 단계 | 담당 | 입력 → 출력 |
|---|---|---|---|
| ① | **Planner** | Claude | `brief.md` → `plan.json` (핵심 메시지 1문장, 근거 3~5개, 플랫폼별 앵글, CTA, 금지사항) |
| ② | **Writer ×4** | Claude (병렬 4회) | `plan.json` + `prompts/<platform>.md` + `platforms.yaml` 제약 → `<platform>/post.json` |
| ③ | **Media Director** | Claude | `plan.json` + `brief` 첨부자료 목록 → `media_plan.json` (어떤 미디어를 어떤 템플릿·문구로 만들지) |
| ④ | **Media Renderer** | Python (Pillow / Playwright / ffmpeg) | `media_plan.json` → 플랫폼별 규격의 JPG / GIF / MP4 |
| ⑤ | **Validator** | Python (LLM 없음) | `post.json` → 통과 / 위반 목록. 위반 시 Writer에 피드백과 함께 재요청 |
| ⑥ | **Reviewer** | Claude (저비용 모델) | 4개 `post.json` + 미디어 썸네일 → `review.json` (플랫폼 적합도 점수, 리스크 플래그, 대안 문구) |
| ⑦ | **Packager** | Python | 전부 → `output/<run_id>/` 폴더 + `REVIEW.md` |

---

## 4. 입력: 브리프 (`briefs/*.md`)

사람이 쓰는 유일한 입력. 예시는 `brief.example.md` 참고.

```yaml
---
title: "v2.0 릴리즈 — 실시간 협업 기능"
goal: announce          # announce | educate | engage | recruit | promote
audience: "개발자, 얼리어답터"
tone: "친근하지만 전문적"
language: [ko, en]      # 플랫폼별 override 가능 (예: reddit/linkedin은 en)
cta: "GitHub에서 ⭐ 누르고 베타 신청"
links:
  - https://example.com/release
assets:                 # 선택. 없으면 템플릿으로 생성
  - assets/stock/dashboard.png
  - assets/stock/demo.mp4
media:                  # 플랫폼별로 어떤 미디어를 원하는지
  default: [jpg]
  x: [jpg, gif]
  telegram: [jpg, mp4]
platforms: [telegram, x, reddit, linkedin]
---
## 핵심 내용
- 실시간 커서 공유 ...
- 지연시간 50ms → 12ms ...

## 피해야 할 표현
- "혁명적", "업계 최초"
```

---

## 5. 플랫폼 섹션 설계

플랫폼별 하드 제약은 `config/platforms.yaml`, 글쓰기 톤·구조는 `prompts/<platform>.md`에 분리.
*제약(코드가 검사)* 과 *스타일(LLM이 따름)* 을 섞지 않는 것이 포인트.

### 4.1 Telegram — "공지 채널 / 커뮤니티 메시지"
- **구조**: 굵은 헤드라인 1줄 → 본문(짧은 문단·불릿) → 링크 → 이모지 적당히
- **제약**: 본문 4,096자, 미디어 캡션 1,024자. 미디어 첨부 시 캡션 길이로 제한됨 → **캡션 버전 + 풀텍스트 버전 둘 다** 생성
- **포맷**: Telegram HTML(`<b>`, `<i>`, `<a>`) 또는 MarkdownV2. 기본 HTML
- **미디어**: JPG 1280×720, MP4(H.264, ≤50MB), GIF는 Telegram이 MP4로 변환하므로 **GIF 요청 시 MP4도 함께 출력**
- **산출물**: `post.json{ text_html, caption_html, text_plain }`

### 4.2 X — "짧고 날카롭게, 스레드 가능"
- **구조**: 단일 트윗(≤280자, 링크는 23자로 계산) 또는 스레드(훅 트윗 + 2~5개 후속)
- **제약**: 280자/트윗, 해시태그 0~2개, 이미지 최대 4장, GIF 1개(≤15MB), 비디오 ≤2:20
- **미디어**: JPG 1600×900(16:9) 또는 1080×1080, GIF ≤15MB, MP4 ≤512MB
- **산출물**: `post.json{ tweets: [ {text, media_refs} ], hashtags, alt_text }` — 첫 트윗이 훅

### 4.3 Reddit — "홍보 아닌 가치 제공, 서브레딧 문화 존중"
- **구조**: 제목(≤300자, 클릭베이트 금지, 핵심 사실 포함) + 본문(마크다운, 배경→내용→질문으로 토론 유도)
- **제약**: 해시태그 금지, 외부 링크는 본문 하단, 서브레딧별 플레어/규칙(브리프에서 `subreddits:` 지정 가능)
- **미디어**: JPG 1200×628 또는 정방형, GIF, MP4 ≤1GB/15분. 이미지 포스트 vs 텍스트 포스트 둘 다 생성
- **산출물**: `post.json{ title, body_markdown, suggested_subreddits, flair, post_type }`

### 4.4 LinkedIn — "전문가 톤, 첫 2줄이 전부"
- **구조**: 훅 1~2줄(접기 전 ~210자) → 빈 줄 → 본문(짧은 문단, 인사이트/숫자) → CTA → 해시태그 3~5개
- **제약**: 3,000자, 해시태그 3~5개, 링크는 본문보다 첫 댓글 권장 → `first_comment` 필드 별도 생성
- **미디어**: JPG 1200×627 또는 1080×1350(4:5, 피드 점유율 최대), MP4 3초~10분, 선택적 PDF 캐러셀(2단계)
- **산출물**: `post.json{ text, first_comment, hashtags, alt_text }`

---

## 6. 미디어 생성 설계

### 5.1 소스 3종 (플러그인 구조)

| 소스 | 방식 | 용도 |
|---|---|---|
| **template** | HTML/CSS 템플릿(`templates/image/*.html`) + 브랜드 토큰 + LLM이 쓴 오버레이 문구 → Playwright 스크린샷 → JPG | 공지 카드, 인용 카드, 숫자 강조, 비교표 |
| **asset** | 브리프에 첨부된 사용자 이미지/영상 → 플랫폼 규격으로 크롭·리사이즈·워터마크 | 스크린샷, 데모 영상 |
| **ai_image** *(선택, 후순위)* | 외부 이미지 생성 API 어댑터 | 템플릿으로 표현 어려운 비주얼 |

Media Director가 `media_plan.json`에 소스와 파라미터를 정하고, Renderer는 그대로 실행만 한다.

### 5.2 포맷별 렌더링

- **JPG**: 템플릿 → PNG 스크린샷 → 플랫폼별 크기로 리사이즈 → JPG(q=90). 플랫폼별 변형은 **같은 템플릿을 다른 뷰포트로 재렌더** (크롭 아님)
- **GIF**: 템플릿 프레임 3~6장(슬라이드 전환) 또는 asset 영상 구간 → ffmpeg `palettegen/paletteuse` → GIF(≤15MB 목표, 초과 시 fps·크기 자동 다운스케일). 항상 **MP4 쌍둥이** 동시 출력
- **MP4**: 슬라이드 + Ken Burns 줌 + 자막 번인(ASS) + 선택적 BGM(`assets/audio/`) → H.264/AAC, 플랫폼별 길이·용량 제한 검사

### 5.3 브랜드 토큰 (`config/brand.yaml`)
색상, 폰트, 로고 위치, 워터마크 여부. 템플릿은 토큰만 참조하므로 브랜드 바꿔도 템플릿 수정 불필요.

---

## 7. 산출물 구조 (검토 패키지)

```
output/2026-11-03_v2-release/
├── REVIEW.md              ← 사람이 보는 한 장 요약 (4플랫폼 텍스트 + 미디어 썸네일 + 리뷰 점수)
├── brief.md               ← 입력 사본
├── plan.json
├── media_plan.json
├── review.json
├── telegram/
│   ├── post.json
│   ├── post.html          ← 복붙용
│   ├── caption.html
│   ├── card_1280x720.jpg
│   └── demo.mp4
├── x/
│   ├── post.json
│   ├── thread.txt         ← 트윗별로 --- 구분, 복붙용
│   ├── card_1600x900.jpg
│   ├── teaser.gif
│   └── teaser.mp4
├── reddit/
│   ├── post.json
│   ├── post.md
│   └── card_1200x628.jpg
└── linkedin/
    ├── post.json
    ├── post.txt
    ├── first_comment.txt
    └── card_1080x1350.jpg
```

단독 모드는 같은 구조에서 플랫폼 폴더가 하나만 생기고 폴더명이 `output/2026-11-03_x-dev-tip-013_x/`처럼 접미사를 가진다.

`REVIEW.md`에는 각 플랫폼마다 **텍스트 / 글자수·제한 / 미디어 미리보기 / Reviewer 코멘트 / 수정 제안**이 표로 들어간다.

---

## 8. LLM 호출 설계

| 단계 | 모델 | 출력 형식 | 비고 |
|---|---|---|---|
| Planner | `claude-opus-5-5` | Structured output (JSON 스키마) | effort `high`, 브리프 전체 + 첨부 이미지 vision 입력 |
| Writer ×4 | `claude-opus-5-5` | Structured output | 4개 병렬(asyncio). 재시도 시 Validator 위반 목록을 user 턴에 추가 |
| Media Director | `claude-opus-5-5` | Structured output | 사용 가능한 템플릿 목록·asset 목록을 컨텍스트로 제공 |
| Reviewer | `claude-haiku-5-5` (기본) / `claude-sonnet-5-5` | Structured output | 비용 절약용. 미디어는 썸네일(≤1024px)로 vision 입력 |

공통:
- SDK: `anthropic` (Python). `thinking` 파라미터 생략(adaptive), `output_config.format`으로 JSON 강제 → 파싱 실패 없음
- `fallbacks: "default"` + beta `server-side-fallback-2026-07-01` 활성화(안전 분류기 거절 시 자동 대체)
- `system` 프롬프트 = `prompts/system.md` + `prompts/<platform>.md` + `platforms.yaml` 해당 섹션. 고정 부분을 앞에 두고 `cache_control` 적용 → 4개 Writer가 캐시 공유
- 모든 호출의 `usage`를 `output/<run>/usage.json`에 기록

예상 비용: 1회 실행(4플랫폼) ≈ 6~8회 호출, 입력 ~30K·출력 ~8K 토큰 → 대략 **$0.3~0.5/런** (Opus 5.5 기준).

---

## 9. Validator 규칙 (코드, LLM 없음)

- 글자 수: X는 Twitter 방식(링크 23자, 이모지 2자), 나머지는 유니코드 코드포인트
- 해시태그 수 범위, Reddit은 0 강제
- 브리프 `avoid` 표현 포함 여부(대소문자·공백 무시)
- 링크 수 / 링크 위치(LinkedIn은 본문 링크 경고)
- 미디어: 해상도·용량·길이·코덱 검사(ffprobe)
- 언어: 브리프 `language`와 불일치 시 경고
- 위반은 `{rule, field, actual, limit, message}` 형태로 Writer 재호출 프롬프트에 그대로 주입

---

## 10. 코드 구조 (2단계 구현 예정)

```
src/community_agent/
├── cli.py              # `community run briefs/x.md`, `community render <run>`, `community review <run>`
├── brief.py            # frontmatter 파싱·검증 (pydantic)
├── llm.py              # Anthropic 클라이언트 래퍼: structured output, 캐시, fallbacks, usage 로깅
├── planner.py
├── writers/
│   ├── base.py         # 공통 Writer 루프(생성 → validate → 재시도)
│   ├── telegram.py
│   ├── x.py
│   ├── reddit.py
│   └── linkedin.py
├── media/
│   ├── director.py     # media_plan.json 생성
│   ├── render_image.py # Playwright 템플릿 → JPG
│   ├── render_gif.py   # ffmpeg
│   ├── render_video.py # ffmpeg + ASS 자막
│   └── specs.py        # platforms.yaml의 media 섹션 → 리사이즈/검사
├── validate.py
├── reviewer.py
├── package.py          # output 폴더 + REVIEW.md
└── publishers/         # 2단계: telegram_bot.py, x_api.py, reddit_praw.py, linkedin_api.py
```

의존성: `anthropic`, `pydantic`, `pyyaml`, `python-frontmatter`, `pillow`, `playwright`, `jinja2`, `ffmpeg-python`(또는 subprocess), `rich`(CLI 출력)

---

## 11. 실행 흐름 (사용자 관점)

```bash
# 1. 브리프 작성
cp brief.example.md briefs/2026-11-03_v2-release.md && vim briefs/2026-11-03_v2-release.md

# 2. 전체 실행 (캠페인) — 또는 단독/배치, '실행 모드' 절 참고
community run briefs/2026-11-03_v2-release.md
#   → output/2026-11-03_v2-release/REVIEW.md 열어서 검토

# 3. 일부만 재생성 (예: X 문구만 다시, 미디어는 유지)
community rewrite output/2026-11-03_v2-release --platform x --note "더 짧게, 숫자 강조"

# 4. 미디어만 재렌더 (템플릿 수정 후)
community render output/2026-11-03_v2-release --only gif
```

---

## 12. 2단계 확장 포인트

- **Publishers**: `post.json` + 미디어 경로를 받아 각 API로 업로드. Telegram Bot API, X API v2, Reddit(PRAW), LinkedIn Marketing API. `REVIEW.md`에서 승인 체크 후 `community publish <run> --platform x`
- **스케줄링**: 승인된 런을 `queue.json`에 넣고 cron / Managed Agents scheduled deployment로 발행
- **성과 피드백**: 발행 후 지표(좋아요·클릭)를 가져와 다음 Planner 컨텍스트에 "과거 성과 좋은 패턴"으로 주입
- **PDF 캐러셀(LinkedIn)**, **Reddit 서브레딧 규칙 자동 조회**, **ai_image 어댑터**

---

## 13. 가정 및 확인 필요 사항

| 항목 | 현재 가정 | 바꾸려면 |
|---|---|---|
| 언어 | Python 3.11+ | TypeScript도 가능(Playwright·ffmpeg 동일) |
| 이미지 생성 | HTML 템플릿 렌더 + 사용자 asset 중심, AI 이미지 생성은 선택 플러그인 | 처음부터 AI 이미지가 필요하면 `ai_image` 어댑터를 1단계에 포함 |
| 포스트 언어 | 브리프에서 지정, 기본 ko+en 병행 (Reddit/LinkedIn은 en) | `platforms.yaml`의 `language` 기본값 수정 |
| 브랜드 | 로고·색·폰트 미확정 → `brand.yaml` 플레이스홀더 | `assets/logo/`, `assets/fonts/`에 파일 넣고 `brand.yaml` 채우기 |
| 디자인 톤앤매너 | Mobbin의 Cloud Studio 화면을 레퍼런스로 지정받음. 로그인 벽 때문에 아직 미확인 | 캡처 3~5장을 `assets/reference/`에 넣으면 색·타이포·여백·라운드 값을 추출해 `brand.yaml`과 템플릿에 반영 |
| 콘텐츠 주제 | 미확정(제품/프로젝트/개인 브랜드 등) | 첫 브리프에서 자연히 드러남. Planner 프롬프트에 "정체성" 섹션 추가 가능 |
