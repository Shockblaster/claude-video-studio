# Puppet parts prompts (ChatGPT image gen, concept image attached)

Start each prompt with "Create an image. " + LOCK + BG + one LAYOUT. One fresh chat per sheet.

**LOCK (2D example):** Use EXACTLY this cartoon character from the attached character sheet: same face, <features>, <outfit>, same flat 2D cartoon style, same outline weight and colours.

**LOCK (3D example):** Use EXACTLY this 3D animated character from the attached character sheet: same face, <features>, <outfit>, same stylised 3D animated feature-film render style, same soft studio lighting and materials. (If the concept drifted photo-real, add: render MORE STYLISED, slightly bigger expressive eyes, softer simplified features, clearly animated, NOT photoreal.)

**BG:** Background: solid flat pure chroma green #00FF00 everywhere, no floor shadow, no gradient, no text, no letters, no numbers, no logos.

**POSE:** LAYOUT: square image, a 2 by 2 grid of four waist-up figures, each figure fully separated from the others by WIDE empty green gaps, no hand or arm touching or crossing into another figure or the image edge. All four facing the viewer, identical size, identical head position within its cell, identical face (neutral pleasant expression, mouth closed). Only the arms differ: top-left both arms relaxed down at the sides; top-right right hand raised with index finger pointing up; bottom-left one open palm presenting out to the side at chest height, kept inside its cell; bottom-right both hands in front of the chest counting on fingers. Hands anatomically correct, five fingers each.

**MOUTH:** LAYOUT: landscape 3:2 image, a 3 by 3 grid of the SAME front-facing head and shoulders, each cell separated by green gaps, identical in every cell (same head angle, size, position, eyes open, same brows) EXCEPT the mouth. Mouths, left to right, top to bottom: 1) closed relaxed smile, 2) lips pressed together as for M/B/P, 3) teeth together slightly parted as for S/T/EE, 4) open as for EH, 5) wide open as for AA with tongue visible, 6) rounded open O, 7) small puckered OO, 8) top teeth resting on lower lip as for F/V, 9) open with tongue tip up behind the teeth as for L.

**EYES:** LAYOUT: landscape 3:2 image, a 3 by 2 grid of the SAME front-facing head and shoulders, each cell separated by green gaps, identical in every cell (same head angle, size, position, mouth closed relaxed smile) EXCEPT the eyes and eyebrows: 1) eyes open, brows neutral, 2) eyes half closed, 3) eyes fully closed (blink), 4) eyebrows raised high, eyes wide (surprise), 5) eyebrows furrowed and angled, eyes slightly narrowed (thinking), 6) eyes open looking to the side, brows neutral.

Pull results with the in-page base64 fetch (`references/browser-ai.md`); generated images may be lazy-loaded: scroll the thread before reading `img` elements, and filter by naturalWidth > 500 rather than alt text (alt varies: "Generated image 1" or empty).
