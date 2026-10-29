# Retention playbook

How a short keeps people watching, sharing and coming back. Two kinds of statement live
here, kept apart on purpose:

- **Platform-stated** (verified): Instagram has named watch time (share of the video
  watched), likes per reach and **sends per reach** (DM shares) as its main Reels ranking
  signals, and in 2026 says sends carry extra weight. YouTube and TikTok likewise rank on
  watch time and completion. Loops replay, and a replay counts as watch time.
- **Craft heuristics** (not data): the timings and rules below are working defaults.
  Replace any of them with the brand's own numbers once `performance.md` has them.
  Third-party "benchmarks" found online (3-second hold rates and the like) were not
  verifiable, so none are quoted as fact.

## 1. The retention grid (20-45 s default)

| Time | Beat | Job | Rule |
|---|---|---|---|
| 0.0-0.3 s | Frame 1 | Stop the thumb | Frame 1 already shows the hook visual and text. No logo, no fade from black, no "hi guys" |
| 0.3-1.5 s | Hook | Create a question the viewer needs answered | One line of on-screen text (max ~7 words) + motion that starts immediately |
| 1.5-3 s | Promise | Say what they get and why it is worth staying | "In 30 seconds you'll know…" or show the payoff blurred / half-built |
| every 5-7 s | Re-hook | Reset attention | Switch visual mode (2D to 3D, chart to avatar, wide to punch-in), a new sound, a new question |
| ~40-50% | Open loop | Keep them past the middle | "But the real problem is the third one" / a counter that is still running |
| ~70-80% | Climax | The payoff, the most surprising true fact | Built up (riser, slow-down, freeze), then released (number slam, hit SFX, colour shift) |
| last 2-4 s | Share + loop | Earn the send, restart cleanly | Share prompt tied to a person ("send this to the friend who…"), the last frame matches frame 1 so the replay is seamless |

Length: aim for the shortest cut that still lands the climax. 20-35 s is the default
sweet spot for explainers. Go longer only when every 5 s still earns its place.

## 2. Hooks

A hook must be TRUE and SPECIFIC. Every hook number traces to `sources.md`.

| Archetype | Shape | Example skeleton (fill with real, sourced facts) |
|---|---|---|
| Counterintuitive number | A number that breaks a belief | "Rs X a month became Rs Y. Nobody added more money." |
| Myth bust | Name the belief, then break it | "Saving more is NOT how most people get rich." |
| Hidden cost | Show what they are losing now | "This one setting is quietly costing you Rs X a year." |
| Comparison | Two choices, a surprising winner | "Same salary, same age. One retires 10 years earlier." |
| Common mistake | "You're doing X wrong" with stakes | "90% of people pick the wrong…" (only with a real source for the 90%) |
| Direct question | A question they cannot ignore | "Do you actually know what your SIP returns after tax?" |
| Before / after | The transformation in one frame | Split screen, number morphs from A to B |
| Insider reveal | What professionals know | "Advisers check this first. Most people never look at it." |
| Calendar urgency | A real deadline or event | "Budget day changed this. Here's what it means for you." |

Hook craft rules:
- Text hook and visual hook say the same thing. The voice can add, never contradict.
- Start mid-motion: the first frame already has something moving or half-revealed.
- Use the viewer's own words ("salary", "EMI", "tax") rather than jargon.
- Hindi/Hinglish: hook text in the script the audience reads most (brand pack decides).
- Write three hooks, score each 1-5 on: specific, true, curiosity gap, visual in frame 1,
  relevant to the target viewer. Use the highest; keep the runner-up for an A/B repost.

From the MAKINGAIDOIT Free Reel Kit (2026-10-29: a creator's own rules from their insights; not
verified by our numbers yet, so re-rank with `performance.md`):
- The text hook is on screen from the very FIRST frame. That frame is also the thumbnail.
- If the skip rate is above ~60%, change only the first 2 seconds and keep the body.
- Never repost the same body. The guide says Instagram flags it as "already shared". A repost
  needs a new voice and new visuals, not just a new hook.
- Hooks that show the payoff in frame one (a result, a price, a thing doing something
  surprising) beat hooks that only promise it.

## 3. Re-hooks and pacing

- Visual change every 1.5-3 s (cut, move, morph, new element). A full mode switch every
  5-7 s. Measured since 2026-10-29: `scripts/pace_check.py` flags any stretch over 1 s where
  nothing behind the avatar changes, and the first 2 s must never sit still.
- Kill dead air: no beat of VO without matching motion, no motion without purpose.
- Pattern interrupts that work: punch-in zoom, a 3D camera move, the avatar entering or
  pointing, a sound hit, a colour flip, a question on screen.
- Captions on screen the whole time (most people watch muted), max 3-4 words per group,
  the key word highlighted.

## 4. Climax

The climax is the single most eyebrow-raising TRUE fact in the video, saved for ~75%.
- Build: tension music or a riser 1-2 s before, the frame tightens or slows, a counter
  speeds up.
- Release: the number lands big (slam, scale overshoot), a hit SFX on the exact frame,
  a colour or light shift, then 0.5-1 s of hold so it can be read.
- After the climax, wrap in under 5 s. Nothing new after the payoff except the share
  prompt.

## 5. Shareability (sends per reach)

People send a video when it says something about them or the person they send it to.
- **Tag-a-person framing**: "send this to the friend who still keeps money in a savings
  account". Name the type of person, not "share this".
- **Relatable moments**: salary day, the first EMI, a parent's advice, a wedding budget.
- **Save-worthy utility**: a framework, a checklist, a number to remember. Saves and
  sends often travel together.
- **Calendar moments**: tie topics to dates people are already talking about (budget day,
  tax deadlines, festivals, results season). The brand pack keeps its own calendar.
- **Status for the sender**: content that makes the sender look smart or caring.
- Avoid: content only the brand cares about, hard selling, anything that would embarrass
  the sender.

## 6. Eyebrow-raisers

Moments that make someone go "wait, what?". Use 2-3 per video, all true.
- A real statistic with its source shown on screen (small, under the number).
- Scale made visible: Rs 1 crore as a stack, a 30-year line drawn in 3 s.
- A live counter: "while you watched this, X happened" (sourced rate, honest maths).
- A reversal: the obvious answer turns out wrong.
- Precise beats round: "Rs 2,37,000" is more believable than "Rs 2 lakh+".

## 7. Topic engine

Score each candidate topic 1-5 on:
1. Audience pain or curiosity (does the target viewer already worry about this?)
2. Brand relevance (does it lead naturally to what the brand does?)
3. Share potential (is there a person you would send it to?)
4. Surprise available (do we have a true, sourced eyebrow-raiser?)
5. Timeliness (a calendar moment now) or evergreen value
6. Visual potential (can it be shown, not just said?)

Shoot only topics scoring 20+ of 30. Keep the bank and the calendar in the brand pack
(`topics.md`). Mix: ~60% evergreen explainers, ~25% timely, ~15% myth-bust or reaction.
Series formats ("Money myth #3") build return viewers. Re-rank by `performance.md`.

## 8. Endings and loops

- The last frame visually matches frame 1 (same layout, same element) so the loop reads as
  one continuous film.
- The final VO line can lead back into the first ("…and that's why" → frame 1 "Rs X…").
- CTA: one ask only. Follow, comment a word, or send. Never three.
- Leave the brand's required disclaimer slot clear (brand pack decides content and
  duration).

## 9. Self-score before the user sees it (1-5 each)

Hook in frame 1 · promise by 3 s · visual change rate · re-hook every 5-7 s · climax
build and release · caption legibility at phone size · audio mix · share prompt · loop
seam · facts sourced. Anything below 4: fix first, or tell the user why it stays.
