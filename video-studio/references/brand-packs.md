# Brand packs

`video-studio` is brand-neutral. Everything specific to one brand or project lives in a
brand pack, so the studio skill can serve any number of brands.

## Shape
A skill folder `~/.claude/skills/<brand>-reels/` with:

| File | Holds |
|---|---|
| `SKILL.md` | Triggers on the brand's name; says "load `/video-studio` first"; lists the files below and the brand's hard rules |
| `brand.md` | Who the brand is, audience, tone, languages, logo files, voices picked in the bake-off, characters/avatars, contacts for approvals |
| `MOTION.md` | Colours (hex), fonts (with file paths and licences), type scale, motion personality, allowed and banned effects, caption style, sonic identity |
| `topics.md` | Topic bank with scores, content pillars, the brand's calendar moments, series formats |
| `hooks.md` | Hooks that fit the brand, re-ranked by results |
| `compliance.md` | Regulatory or legal rules: banned claims, disclaimer slot, who approves |
| `performance.md` | Posted videos with real metrics, and what they taught |
| `assets/` | Logos, character rigs, music beds, brand SFX (or a pointer to where they live) |

A studio project folder for the brand (e.g. `~/video-projects/<brand>-reels/`, on the drive with the most space) holds the
per-video HyperFrames projects, voice bake-offs and renders. Its `CLAUDE.md` says to load
`/video-studio` and the brand pack.

## Making one
1. Ask for: logo files, website, 3-5 reference frames or videos they like, audience,
   languages, any regulator or legal limits, people who will appear.
2. Run `/brand-intake` for brand.md + MOTION.md from those answers and frames; then move
   the files into the pack and add the sections above it does not cover.
3. Pull real colours and fonts from the brand's site or design files, never guessed.
4. Voice bake-off (`voice.md`) and, if wanted, characters (`avatars.md`).
5. Seed `topics.md` with 10-20 scored topics and `hooks.md` with the archetypes that fit.
6. Copy `templates/brand-pack-template/SKILL.template.md` to the new pack as `SKILL.md` and fill it in.
