# Planner

Input: the full brief (frontmatter + body), plus any attached images.
Output: `plan.json`

Decide, before anyone writes a word:
1. `core_message` — one sentence the audience should remember.
2. `proof_points` — 3–5 concrete facts/numbers from the brief, ranked by strength.
3. `angles` — for each platform, the ONE angle that fits its culture:
   - telegram: what the community needs to know / do now
   - x: the hook that stops scrolling (a number, a contrast, a bold-but-true claim)
   - reddit: the useful or technical story, not the product
   - linkedin: the professional insight or outcome
4. `cta_variants` — CTA phrased per platform.
5. `media_hints` — per platform: which proof point should be the visual, and whether a template card, a user asset, or a short clip serves it best.
6. `risks` — anything that could read as misleading, spammy, or violate a platform norm.
7. `open_questions` — missing facts the human should fill in before publishing.

Mode:
- `campaign` (2+ platforms): do everything above; make sure numbers and claims are identical across angles.
- `single` (1 platform): produce `core_message`, `proof_points`, the one `angle`, `cta`, `media_hint`, `risks`, `open_questions`
  for that platform only. Do not invent angles for platforms that were not requested.
