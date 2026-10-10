# Bússola — experience structure V1

**Run:** `bussola-public-case-v1`  
**Agent contract:** `experience-designer`  
**Inputs:** context packet + reference synthesis + narrative architecture

## 1. Experience goal

The case should let a reader answer, without reconstructing the project from footnotes:

- What did the team notice?
- Why did that change the product idea?
- What did Bússola explore?
- What was actually built in the hackathon?
- What changed later in UX/content?
- What is still hypothesis?
- Who contributed?

The experience should reward both a 90-second scan and a deeper product/design read.

## 2. Information hierarchy

### Level 1 — story beats

Visible through headings and large evidence:
- contradiction;
- discovery;
- Fernando;
- product decision;
- PoC;
- UX evolution;
- prototype;
- team/colophon.

### Level 2 — proof

Real or clearly labelled artifacts:
- synthetic-data relationship;
- product/UI states;
- architecture/documentation;
- prototype;
- repository/history;
- team portraits.

### Level 3 — limits/provenance

Short notes adjacent to the artifact:
- synthetic dataset;
- persona/AI image;
- reconstruction;
- architecture vs implementation;
- unvalidated behavior.

### Level 4 — deep technical sources

Links/expanded source trail:
- repository docs;
- architecture;
- commits;
- code;
- detailed provenance.

Do not force Level 4 into the primary scroll.

## 3. Global page behavior

### Navigation

Use a small, direct table-of-contents/navigation treatment.

Primary anchors:
- Descoberta
- Produto
- Evolução
- Protótipo
- Equipe

Avoid:
- translucent blur nav;
- pill navigation;
- persistent UI that competes with the case.

On mobile, navigation can collapse to a simple index/menu, but all major sections remain accessible without hover.

### Reading width

Long-form paragraphs need a stable readable measure. Visual artifacts may break the text column and use wider/full-width zones.

The case should not force every section into one universal max-width.

## 4. Section structure

### 0 — Hero

**Immediate content**
- headline;
- short intro;
- one visual scene;
- minimal event/case metadata;
- optional text link to start the story.

**Scene rule**
One visual relationship only. No multiple evidence cards.

The scene may combine:
- Fernando;
- one UI state;
- controlled crop/overlap.

The debt/rotativo insight belongs below in Discovery.

**Provenance**
Fernando + UI provenance as a low-contrast caption associated with the scene.

**Mobile**
Recompose, do not stack:
- headline/intro first;
- then one cropped Fernando + UI scene;
- preserve a visible spatial relationship;
- no requirement to show the full phone/device.

Motion has **no essential job** here. Entrance motion may be considered later only if the static scene already passes.

---

### 1 — Discovery

**Purpose**
Make the product-origin insight graspable in seconds.

**Immediate content**
- “Não escolhemos o problema antes de olhar os dados.”
- the qualitative relation:
  - saldo positivo;
  - uso do rotativo;
- one sentence explaining why this mattered.

**Evidence treatment**
Use a ledger/analysis relationship, not a generic data card.

Possible interaction:
- none required.

If source detail needs expansion, use a small “Como chegamos aqui / Fonte” disclosure after the main relation.

**Mobile**
The relation must remain one semantic object. Do not split it into disconnected cards.

Motion: **no job**.

---

### 2 — Fernando

**Purpose**
Show the human consequence of the financial contradiction.

**Immediate content**
- Fernando;
- goal;
- the key question: what already competes with that goal?

Avoid replaying the exact hero image/pose at the same scale.

Possible treatments:
- closer crop;
- selected UI detail;
- short editorial quote/statement.

**Mobile**
Image and text may reorder, but the provenance stays attached to the image.

Motion: **no job**.

---

### 3 — Product decision

**Purpose**
Bridge research → interface.

**Immediate content**
A short progression such as:

`objetivo → contexto → cenário → decisão → consentimento`

Each step should explain a product decision, not a feature list.

**Progressive disclosure**
Technical implementation details stay out of this section.

**Mobile**
Horizontal process becomes a vertical sequence with explicit step numbers/labels. No carousel required.

Motion: optional only if it helps reveal the progression; not required.

---

### 4 — PoC / architecture

**Purpose**
Show technical ambition and bounded implementation.

**Immediate content**
- one large architecture artifact or faithful excerpt;
- a short explanation of how the pieces support the product idea;
- clear PoC/architecture limit.

**Secondary detail**
- stack;
- repository/commit evidence;
- links to technical docs.

Do not convert the stack into decorative chips.

**Desktop**
Architecture may occupy the wide visual field with annotations or a side note.

**Mobile**
Use:
- responsive redraw only if it remains faithful to the documented architecture; otherwise
- horizontal pan/zoom/open-full-size behavior with an accessible text summary.

Motion: **no job**.

---

### 5 — UX evolution

**Purpose**
Demonstrate design/content-design craft.

**Content**
Keep the four documented decisions:
1. entry;
2. financial effort;
3. consent;
4. legibility.

**Comparison rule**
Each pair answers one question:
- What was unclear?
- What changed?
- What does the person understand now?

Do not add a separate “design-system” layer around the comparison.

**Desktop**
- one pair per spread/visual beat;
- UI large enough to read;
- minimal device chrome;
- annotation close to the change.

**Mobile**
- Before then After;
- labels remain sticky/obvious within the pair;
- no slider that hides one state;
- no flip interaction;
- UI text remains readable without pinch zoom where feasible.

**Progressive disclosure**
Long rationale can sit below the pair; the visual change must be understandable before opening it.

Motion: **no job** for the comparison itself.

---

### 6 — Prototype

**Purpose**
Let the reader inspect the experience.

**Immediate content**
- “Experimentar a PoC” / equivalent;
- a short scope note;
- embedded prototype or clear launch action.

**Interaction**
If iframe remains:
- keyboard focus must be visible;
- escape/navigation behavior should be understandable;
- provide an external/open-full link;
- do not trap the user in the embed.

**Mobile**
If embedded experience is too constrained, prefer a strong launch action plus selected static evidence rather than a tiny unusable iframe.

Motion: only product-native motion inside the prototype; no decorative wrapper motion required.

---

### 7 — Team

**Purpose**
Show collective authorship and the hackathon context.

**Immediate content**
- group/people;
- names;
- actual contribution;
- mentor.

**Secondary**
Short trajectory and profile link.

Avoid:
- corporate leadership cards;
- flip/hover to reveal essential text;
- identical headshot grid if a more documentary composition is available.

**Mobile**
Readable credits in linear order. No horizontal carousel required.

Motion: **no job**.

---

### 8 — Colophon

**Purpose**
End with precision.

Three short groups:
- observed;
- explored/built;
- refined later.

Then:
- what remains hypothesis;
- code/prototype/sources.

No dual sales CTA.

## 5. Scan path

A scanning reader should be able to understand the case from:

1. headline;
2. Discovery relation;
3. Fernando goal;
4. product-decision progression;
5. architecture artifact;
6. before/after pairs;
7. final “what this proves” colophon.

If this path works, body copy can support depth instead of carrying the whole story.

## 6. Progressive disclosure map

Use disclosure only for:
- source trails;
- long technical detail;
- extended mini-bios;
- detailed implementation notes.

Do **not** hide:
- critical limitations;
- before/after states;
- team contribution;
- synthetic/persona provenance;
- product-decision logic.

## 7. Accessibility requirements

- semantic heading hierarchy;
- skip link;
- visible focus;
- no essential hover-only content;
- color not sole carrier of Before/After or financial state;
- reduced-motion path;
- readable UI evidence at 320/390px;
- text alternative/summary for technical visual artifacts;
- iframe/title and focus behavior validated;
- AI-generated/persona provenance available to screen-reader users;
- no claim of full WCAG conformance without assistive-tech review.

## 8. Responsive acceptance criteria

At **1440 / 390 / 320 px**:

- no horizontal page overflow;
- hero remains one authored scene;
- Discovery relation remains one semantic unit;
- product-decision sequence is legible;
- architecture remains inspectable;
- Before/After labels never detach from their states;
- essential UI text remains readable;
- team credits require no interaction;
- source/limit notes remain accessible without dominating the visual hierarchy.

## 9. What not to build yet

Until Art Direction is approved:

- no production CSS refactor;
- no new site-wide color system;
- no hero motion;
- no new card/component library;
- no carousel;
- no decorative data visualization;
- no new architecture diagram that departs from documented evidence.

## 10. Handoff

**Experience structure: READY for Editorial Art Direction.**

Art Direction now owns:
- composition;
- type/image/materiality system;
- scale;
- crop;
- section rhythm;
- visual treatment of evidence.

It may not reopen the narrative/factual boundaries without routing a conflict upstream.
