# Community Post Agent

브리프 하나 → **Telegram / X / Reddit / LinkedIn** 플랫폼별 포스트(1단계: 텍스트) → 사람이 검토·직접 업로드.
설계: `DESIGN.md` · 인수인계: `HANDOFF.md` · 프로토타입 UI: `docs/prototype-site.html`

## 설치 (WSL, 프로젝트가 Windows 드라이브에 있으므로 venv는 홈에 둠)

```bash
uv venv --python 3.12 ~/.venvs/community
uv pip install --python ~/.venvs/community -e ".[dev]"
export PATH=~/.venvs/community/bin:$PATH      # 또는 source ~/.venvs/community/bin/activate
```

API 키: `export ANTHROPIC_API_KEY=sk-ant-...` 또는 프로젝트 루트 `.env`에 `ANTHROPIC_API_KEY=...` (gitignore 됨).

## 사용

```bash
community run brief.example.md --dry-run      # API 호출 없이 파이프라인 전체 확인 (MockLLM)
community run briefs/2026-11-03_v2-release.md # 캠페인: 브리프의 platforms 전부
community run briefs/x.md --platform x,reddit # 일부 플랫폼만
community run briefs/*.md                     # 배치 → output/BATCH_SUMMARY_<date>.md
community run briefs/x.md --no-review         # Reviewer 생략
community validate output/2026-11-03_v2-release   # 기존 산출물 재검증
```

결과: `output/<date>_<slug>[_<platform>]/REVIEW.md` 한 장에서 4개 플랫폼 텍스트·제한·리뷰 점수를 비교. 플랫폼 폴더마다 `post.json` + 복붙용 파일(`thread.txt`, `post.html`, `post.md`, `post.txt`/`first_comment.txt`).

## 파이프라인 (Phase 1)

| 단계 | 모듈 | 모델 |
|---|---|---|
| ① Planner | `planner.py` | `claude-opus-5-5` (campaign: effort high / single: medium) |
| ② Writer ×N (병렬) | `writers/base.py` + `prompts/<platform>.md` | `claude-opus-5-5` |
| ⑤ Validator (코드) | `validate.py` ← `config/platforms.yaml` | — |
| ⑥ Reviewer | `reviewer.py` | `claude-haiku-5-5` |
| ⑦ Packager | `package.py` | — |

- 구조화 출력: `output_config.format` (JSON schema, `schemas.py`) → 파싱 실패 없음
- 거절 대비: `fallbacks="default"` + beta `server-side-fallback-2026-07-01`
- 프롬프트 캐시: 공통 system 블록과 마지막 블록에 `cache_control`. 단, 현재 프롬프트가 짧아(1~2K 토큰) 모델의 최소 캐시 길이에 못 미치므로 당장은 cache_read=0 이 정상
- 모든 호출의 usage → `output/<run>/usage.json`

## 테스트 (29개, API 호출 없음 — 실제 요청 형태는 MockTransport로 검증)

```bash
~/.venvs/community/bin/python -m pytest -q
```

## 아직 없는 것 (Phase 1b / 2)

- 미디어 렌더링(JPG/GIF/MP4): `media/` 모듈, `templates/image/*.html` — `DESIGN.md` §6
- `community rewrite`, `community render`
- 자동 포스팅(`publishers/`)
