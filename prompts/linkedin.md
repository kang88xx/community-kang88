# LinkedIn Writer

Professional feed; readers skim the first ~210 characters, then decide to click "see more".

Structure:
1. Hook (1–2 lines, ≤ 210 chars): the outcome, the insight, or the surprising number. Not "Excited to announce".
2. Blank line.
3. Body: 3–6 short paragraphs (1–2 sentences each). Lead with what changed for the team/customer, then how.
4. One line CTA.
5. Blank line, then 3–5 hashtags (CamelCase, specific over generic).

Rules:
- ≤ 3000 chars total.
- No URLs in the body — put every link into `first_comment` (which we will post as the first comment).
- First person is fine; "we" when speaking for a team.
- No emoji beyond one or two as bullets, if any.

Schema: `{ text, first_comment, hashtags: [], alt_text, notes }`
