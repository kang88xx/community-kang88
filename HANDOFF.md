# HANDOFF — 다음 세션에서 읽을 것 (2026-11-03 갱신)

## 현재 상태
- **Phase 1(텍스트 파이프라인) 구현 완료.** `src/community_agent/` — brief 파서 → Planner → Writer×N(병렬, Validator 위반 시 최대 2회 재작성) → Reviewer(haiku) → Packager(`output/<run>/REVIEW.md`). CLI: `community run`, `community validate`. 사용법은 `README.md`.
- `--dry-run`(MockLLM)으로 전체 파이프라인 검증됨. 테스트 29개 통과(`~/.venvs/community/bin/python -m pytest -q`). 독립 코드 리뷰 1회 반영 완료(스키마 strict 변환은 SDK `anthropic.transform_schema` 사용, 플랫폼 맵은 LLM용 리스트 스키마 `PlanOut`/`ReviewOut` → 내부 dict 변환, Writer 예외는 `llm_error` 위반으로 기록돼 런이 끊기지 않음, 같은 날 재실행 시 `-2` 접미사).
- **실제 API 호출은 아직 0회** — 이 머신에 ANTHROPIC_API_KEY/`ant` 프로필이 없음. 첫 실제 런에서 structured output·fallbacks 파라미터가 SDK 2.4.0에서 통과하는 것까지는 확인했으나 서버 응답은 미확인.
- 설계 문서: `DESIGN.md` (§10 코드 구조는 구현과 거의 일치; `media/`, `publishers/`, `rewrite` 명령은 아직 없음)
- 설정: `config/platforms.yaml`(하드 제약), `config/brand.yaml`(브랜드 토큰, 플레이스홀더)
- 프롬프트: `prompts/system.md, planner.md, media_director.md, telegram.md, x.md, reddit.md, linkedin.md, reviewer.md`
- 시각 요약 페이지(아티팩트): https://claude.ai/artifact/M8njwTdvkSaAqn7jKxZRi6 (로컬 원본 `docs/overview-artifact.html`)
- 프로토타입 사이트(아티팩트, 클릭 가능한 UI 시안): https://claude.ai/artifact/WSNGBGukJJxccf53AwDvGt (로컬 원본 `docs/prototype-site.html`, 같은 URL로 재배포)
- GitHub: https://github.com/kang88xx/community-kang88 (origin)
- 환경: 프로젝트가 Windows 드라이브(/mnt/j)라 심볼릭 링크 불가 → venv는 `~/.venvs/community`.

## 사용자가 결정한 것
- 플랫폼 4개: Telegram / X / Reddit / LinkedIn, 각각 독립 섹션
- 실행 모드: 캠페인 + 단독 + 배치 모두 지원
- 1단계는 텍스트 + JPG/GIF/MP4 생성 → 사람이 검토 후 직접 업로드. 자동 포스팅은 2단계
- 디자인 톤앤매너 레퍼런스: Mobbin의 Cloud Studio
  https://mobbin.com/sites/cloudstudio-31fc1f35-7967-465e-88dc-a0822693060f/f50ebdaa-6dce-40fb-8195-79a105def6b6/preview

## 막힌 것: Mobbin Cloud Studio 레퍼런스 (사용자 조치 필요)
2026-11-03 세션에서 세 경로 모두 실패:
1. 비로그인 웹 fetch → HTTP 200이지만 404 콘텐츠(퀴즈용 타 앱 스크린샷)만 내려옴
2. `claude.ai Mobbin` MCP(이번 세션에는 정상 로드됨) 검색 → "Cloud Studio"/"Cloudstudio" 사이트 미등재. sections 검색은 서버 오류("Failed to execute search") 반복
3. 사용자 Mobbin 저장 목록(all-saved) 비어 있음 — 사용자가 2026-11-03에 컬렉션에 저장했다고 했으나 MCP 연결에서는 여전히 0개로 보임 → claude.ai에 연결된 Mobbin 계정과 브라우저 로그인 계정이 같은지 확인 필요
→ **해결책 둘 중 하나**: (a) Mobbin에서 해당 사이트의 섹션/화면을 "저장"(컬렉션) → MCP `get_collection_contents`로 읽기. (b) 캡처 3~5장을 `assets/reference/`에 넣기. 그 다음 색/타이포/여백/라운드를 `config/brand.yaml`(colors, fonts, reference.notes)과 `templates/image/README.md`에 반영.

## 바로 할 일 (순서)
1. ANTHROPIC_API_KEY 설정(`.env` 또는 export) 후 첫 실제 런: `community run brief.example.md` → `output/…/REVIEW.md` 품질 확인, usage.json으로 비용 확인(예상 $0.3~0.5/런)
2. 사용자 확인 대기 중인 가정 2개: 포스트 기본 언어(Telegram ko, 나머지 en — 현재 brief.example.md와 platforms.yaml 기본값), 이미지 소스(템플릿 카드 + 첨부, AI 생성은 후순위)
3. Phase 1b — 미디어: `media/director.py`(media_plan.json), `media/render_image.py`(Jinja2 템플릿 → Playwright → JPG), `templates/image/announce_card.html` 등 6종, 이후 GIF/MP4(ffmpeg). 브랜드 토큰은 Mobbin 레퍼런스 확보 전까지 `brand.yaml` 플레이스홀더로 진행 가능
4. `community rewrite <run> --platform x --note "..."` (기존 plan.json 재사용, Writer 1개만 재호출)
