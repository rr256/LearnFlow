---
title: LearnFlow Domain Terminology
status: approved
owner: product-and-architecture
last_updated: 2026-08-06
related:
  - ../00-project-context.md
  - domain-model.md
  - entities.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
  - ../adr/ADR-016-learner-onboarding-api-contracts.md
  - ../adr/ADR-017-topic-progress-api-and-schema.md
  - ../adr/ADR-018-weekly-availability-slots.md
  - ../adr/ADR-019-study-goal-planning-preferences.md
  - ../adr/ADR-020-initial-study-plan-generation.md
  - ../development/coding-standards.md
---

# LearnFlow Domain Terminology

## Purpose

Define the canonical vocabulary for LearnFlow. Product documentation, UI copy, backend code, APIs, database names, and AI prompts should use these terms consistently.

## Canonical Terms

| Term | Definition | Usage note |
| --- | --- | --- |
| **Learner** | A person using LearnFlow to pursue a learning goal. | Preferred product/domain term. A future technical `user` account represents the learner's identity. |
| **Learning program** | A structured learning journey, such as GATE CSE. | Generic term; do not hardcode `GATE` into platform-core concepts. |
| **Curriculum** | The organized syllabus for a learning program. | Contains subjects, topics, and subtopics. |
| **Curriculum version** | A particular version of a program's curriculum. | Used because a syllabus can change over time. |
| **Subject** | A major curriculum area, such as Operating Systems or DBMS. | Belongs to one curriculum version. |
| **Topic** | A teachable and trackable unit within a subject. | Primary anchor for plans, resources, progress, quizzes, and revision. |
| **Subtopic** | A smaller unit within a topic. | Use only when finer detail is necessary. |
| **Topic relationship** | A link between topics, such as prerequisite or recommended-before. | Used for learning order and planning. |
| **Learning resource** | A learner-owned or curated study reference. | Includes PDFs, notes, PYQs, formula sheets, and local video references. |
| **PYQ** | Previous-year question. | A verified historical exam question; distinguish it from AI-generated practice. |
| **Examination schedule** | The dated calendar an examining body publishes for one cycle of a learning program, such as GATE 2027. | Reference data with a named source, not learner data. Every learner aiming at that cycle reads the same dates. |
| **Examination cycle** | One occurrence of a recurring examination, identified by a label such as `2027`. | A learning program has many cycles over time; each has its own schedule. |
| **Examination period** | One dated span within an examination schedule: registration, late registration, the examination, or the results announcement. | A single-day event starts and ends on the same day. The stored period types are `registration`, `late_registration`, `examination`, and `results`. |
| **Examination window** | The span from the first published sitting day to the last. | Use this, never a single examination date, unless the examining body has published one. Derived from the examination periods; not stored. |
| **Provisional** | A published schedule whose source says the dates are still liable to change. | The honest default before an examining body confirms. Say so wherever the dates are shown. |
| **Confirmed** | A published schedule whose dates the examining body has confirmed. | Set it only on the examining body's word, never on age or proximity. |
| **Learner setup** | The capability by which a learner establishes their profile, active learning program, and study goal before planning begins. | The canonical name for the capability, wherever it is named: requirements, API documentation, endpoint groupings, and UI copy. It is not only a first-time activity — a learner returns to it whenever their goal changes. |
| **Home screen** | The application's landing screen, which shows the learner's saved learner setup — their profile, their study goal, and the published dates of the examination that goal aims at. | Read-only: it reports what is stored and links to *learner setup* to change it. It is not a *dashboard*; see the row below. Its UI heading is "Your study setup". |
| **Study goal** | The learner's target outcome and deadline. | Aims at an examination cycle, a target completion date, or both — never at neither. |
| **Target date** | A learner's own completion date, for a learner following no published examination. | Not a substitute for an examination window. Leave it empty rather than guessing a paper date. |
| **Availability** | Time the learner can realistically allocate to study. | A planning input, not a measure of commitment or ability. Never presented as a total, a target, or a score. |
| **Availability slot** | The study time available on one day of the week, belonging to one study goal. | A goal holds at most seven, one per day. A slot is a quantity of minutes, not a sitting between two clock times. |
| **Weekly availability** | The whole set of a goal's availability slots. | Saved as a week at a time: the days named become the week, and a day left out is removed. |
| **Day of the week** | One of `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, or `sunday`. | Stored and sent as the `snake_case` name, never as a number. Python, JavaScript, and PostgreSQL disagree about which day is zero, so LearnFlow has no numbering to mis-map. See [ADR-018](../adr/ADR-018-weekly-availability-slots.md). |
| **Kept free** | A day the learner deliberately recorded as having no study time. | Stored as an availability slot of zero minutes. Distinct from a day they have not set, which has no slot at all — the same distinction *Not explored* draws against a topic with no record. |
| **Planning preference** | A choice the learner has made about *how* a study plan should be built, belonging to one study goal. | A planning input beside *weekly availability*, never a measure of anything. A preference the learner has not set is unset, not a default: nothing is invented on their behalf, so a planner meeting an unset preference chooses for itself. See [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md). |
| **Session length** | How long one block of study should be, in minutes. | The learner's preference, stored as `preferred_session_minutes`, from 15 to 480. A **duration**, not a time of day — nothing records when in a day a session falls, for the reason *availability slot* gives. Report it in minutes; a total or an hours figure is planning arithmetic. |
| **Topic order** | Which order a study plan works through the curriculum in. | The learner's preference, stored as `topic_sequencing`: `syllabus_order` follows the syllabus's own order, `prerequisites_first` follows the prerequisite links between topics. Stored and sent as the `snake_case` value; the labels a learner reads are *Syllabus order* and *Prerequisites first*. |
| **Study plan** | A roadmap, monthly plan, weekly plan, or daily plan of recommended work. | Generated against a study goal and current evidence, by deterministic rules rather than by an AI provider. A roadmap and a weekly plan are generated today; see [ADR-020](../adr/ADR-020-initial-study-plan-generation.md). |
| **Superseded plan** | A plan a later generation replaced. | Kept and readable, never deleted: plan history is what makes a change of direction explainable. It keeps the wording it was generated with. |
| **Plan item** | One actionable recommendation in a study plan. | Examples: study, practise, revise, or review mistakes. Its position in the plan is an order, never a score. |
| **Recommendation reason** | The sentence a plan or a plan item gives for itself. | Written when the plan is generated and never rewritten, so a superseded plan still explains itself in the terms that produced it. A statement about the plan's reasoning, not about the learner. |
| **Study activity** | A record of actual study, practice, or revision work completed by the learner. | May record duration and related resources/topics. |
| **Learner topic progress** | The learner-specific state and evidence for one topic. | Combines several signals; it is not a single permanent score. |
| **Material completed** | The learner has completed the planned material for a topic. | Does not mean mastery or exam readiness. |
| **Learning stage** | A supportive, learner-visible summary of current understanding. | Use the approved stage labels below. They are the wording a learner reads; the stored and wire form is the `snake_case` value beside each one, per [ADR-017](../adr/ADR-017-topic-progress-api-and-schema.md). |
| **Not explored** | No meaningful work or evidence is recorded for the topic. | Neutral starting state. Stored as `not_explored`, but a topic with **no record at all** also reads as this — the two are distinct, and only the first means the learner said so on purpose. |
| **Building foundation** | The learner should focus on concepts and basic study. | Use a constructive next action. Stored as `building_foundation`. |
| **Developing confidence** | The learner has partial understanding and needs focused practice. | Do not label this as weak. Stored as `developing_confidence`. |
| **Practice-ready** | The learner is ready for more topic-focused questions. | Not a guarantee of exam performance. Stored as `practice_ready`. |
| **Strong understanding** | Recent evidence indicates consistent understanding; scheduled revision is still needed. | Do not call this permanent mastery. Stored as `strong_understanding`. |
| **Stage source** | Whether a learning stage was set by the learner or derived from evidence. | Stored as `learner`, `derived`, or `mixed`. Everything recorded today is `learner`; nothing derives a stage yet. |
| **Revision** | Intentional revisiting of a topic to reinforce retention and address errors. | A revision record tracks when it is due and what happened. |
| **Revision due** | A topic currently recommended for revision. | A recommendation, not a failure notice. |
| **Checkpoint quiz** | A short, topic-focused practice assessment. | Used to gather evidence after study or revision. |
| **Question / assessment item** | One answerable prompt within a quiz or question bank. | May be AI-generated or from a verified source. |
| **Quiz attempt** | A learner's submitted response to a checkpoint quiz. | Records answers, score, feedback, and mistakes. |
| **External test result** | A learner-entered result from an assessment completed outside LearnFlow. | Canonical term for the whole recorded result. May reference Testbook, Made Easy, or another provider; it is not an integration. |
| **Topic performance evidence** | Topic-specific marks, attempts, or mistakes recorded from an external test result. | Canonical term for the topic-level detail inside an external test result; it belongs to one external test result and one topic. Checkpoint quiz outcomes are never topic performance evidence. Only create it when the external test report actually provides topic-level information. |
| **Mistake evidence** | A recorded error or learning gap. | Initial categories: concept gap, calculation error, careless error, time-management issue. |
| **Priority focus area** | A topic or action currently likely to benefit the learner most. | Prefer this in the UI over “weak topic.” |
| **Mentor** | LearnFlow's AI-assisted guidance role. | Explains, plans, recommends, and reflects; it does not replace learner judgement. |
| **Grounded answer** | An AI response based on retrieved learner resources or verified content. | Identify supporting resources where practical. |
| **RAG** | Retrieval-Augmented Generation. | Technical term for retrieving relevant material before AI generation. |
| **AI provider** | The service/model used to generate AI responses. | Ollama is the initial provider; the domain must not depend on it. |
| **Knowledge base** | Searchable representations of learning resources used for grounded retrieval. | Different from the original resource files and structured learner data. |

## Terms to Avoid or Use Carefully

| Avoid / use carefully | Preferred wording | Reason |
| --- | --- | --- |
| Weak topic; weak area; weakness | Priority focus area; Building foundation | More constructive and action-oriented. Applies to learner-facing copy and to the product documentation that defines it. |
| External test performance | External test result; Topic performance evidence | Use `External test result` for the recorded result and `Topic performance evidence` for topic-level detail. “Performance” alone is ambiguous between the two. |
| Failed topic | Topic needing focused practice | A topic is not a pass/fail judgement. |
| Mastered | Strong understanding | Mastery is difficult to prove and should not be inferred from one signal. |
| Complete | Material completed; plan item completed | Clarify whether material or a planned task was completed. |
| Exam date; examination date | Examination window; examination period | A body that publishes several sitting days has not named the learner's day. A single date presents a guess as a deadline. |
| Exam; GATE date | Examination cycle; examination schedule | Keeps platform-core language reusable across learning programs. |
| Onboarding | Learner setup | Use **learner setup** for the capability. **Onboarding** is permitted for one narrower thing only: the first-time UI flow a learner walks through before they have a profile or a goal. It never names the capability, its endpoints, or the ongoing ability to change a goal — a learner who edits an established goal is not being onboarded. |
| Dashboard (for the home screen) | Home screen | **Dashboard** is reserved for the progress overview [FR-011](../requirements/functional.md#fr-011-progress-overview) describes and PRG-001 will serve: progress by subject and topic, upcoming work, revisions due, and priority focus areas. None of that is built. Calling the setup overview a dashboard would make one word mean two things, and would take the name before the screen that earns it exists. Use **home screen** for the landing screen; the word *dashboard* stays free for progress content. |
| Weekly study hours; total available time | Weekly availability; the availability of one day | A total is planning arithmetic, and it invites a judgement about whether a week is *enough*. FR-003's planner is what should form that view, with the trade-offs visible. It now exists and places work on the days a week names; nowhere else adds a week up, and no screen reports a total. |
| Plan priority (as a rank); most important topic | Plan item order; where an item falls in the plan | `plan_items.priority` is a position counted from 1, not a score. A topic later in a plan is later, not weaker — the same distinction the learning stages draw. Nothing in LearnFlow ranks two topics against each other. |
| Study pace; intensity; study style | Planning preference; session length; topic order | *Pace* and *intensity* sound like settings but define nothing a planner can act on, and they invite a judgement about how hard a learner is working. Name the specific choice being made. |
| Default session length; recommended topic order | An unset planning preference | A preference the learner has not set has no value, and presenting one as a default would report a decision they did not make. Say it is unset, and let the planner choose visibly — which it does, naming the choice as its own. |
| Time slot; study session (for availability) | Availability slot | An availability slot is a quantity of minutes on a day, not a booking between two clock times. Nothing stores a time of day. |
| Test integration | Manual external test result entry | The MVP does not connect to third-party test platforms. |
| AI memory | Learner progress, resource retrieval, or conversation context | Store durable facts in the application/database, not in model memory. |
| GATE topic | Topic in the GATE CSE learning program | Keeps platform-core language reusable. |

## Naming Rules

- Use singular, clear domain names in code and documentation: `Topic`, `StudyPlan`, `QuizAttempt`.
- Use `learner` for product/domain language and reserve `user` for authentication or technical identity when needed.
- Use `learner_id` as the sole identifier for learner-owned records in domain models, database columns, and API contracts. Do not introduce `user_id` as an alternative name for the same relationship; if a distinct authentication identity is added later, it is a separate concept with its own name.
- Use `resource` for a study item; use `document` only when referring specifically to a file format or ingestion process.
- Use `evidence` for observed learning signals; use `stage` for the learner-visible interpretation of that evidence.
- Use `recommendation` for system guidance; avoid wording that makes a recommendation sound mandatory.
- Name a **new** dated span `starts_on`/`ends_on` and a new single day `taken_on`/`due_on`, so the
  name says whether one date or two are meant. Existing names stay as they are: `study_goals.
  target_date` and `study_plans.period_start`/`period_end` predate this rule, and renaming a column
  is a migration decision rather than a wording one.
- State a published date's status wherever it is shown. A provisional date presented without that
  word reads as settled fact.
- A controlled value is stored and sent as `snake_case`; the label in this document is what a learner
  reads. The five learning stages follow the same rule as `late_registration` and
  `recommended_before`, so rewording a label stays a text change rather than a migration over learner
  rows. Keep the two in step: a new stage needs a value, a label, and a next action.
- Name a member of a fixed set by its name, not by its position. The seven days are `monday` to
  `sunday` in the database and on the wire, because an index is the one form of a controlled value
  that can be read wrongly without any error appearing. Where an order is needed — Monday first — it
  is presentation, held in the application rather than stored.
- Name a screen for what a learner does there, not for a UI genre. *Home screen* says where it sits;
  *dashboard* would say what it looks like, and that word is already spoken for above.
- Two existing names retain **onboarding** and are not renamed, for the same reason the dated-span
  rule leaves `target_date` alone — a rename costs more than the inconsistency. The frontend module
  `frontend/features/onboarding/` holds the first-time flow, which the rule above permits; and
  `docs/adr/ADR-016-learner-onboarding-api-contracts.md` keeps its file name because an accepted
  ADR's path is a stable identifier that other documents already link to. Its title uses the
  canonical term. New names use *learner setup*.

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — the examination vocabulary above
- [ADR-016: Fix the learner setup API contracts](../adr/ADR-016-learner-onboarding-api-contracts.md) — the capability *learner setup* names, and the endpoints that serve it
- [ADR-017: Record manual topic progress as a learner-owned stage](../adr/ADR-017-topic-progress-api-and-schema.md) — why the stage labels above and their stored values are separate representations
- [ADR-018: Store weekly availability as named days replaced a week at a time](../adr/ADR-018-weekly-availability-slots.md) — the availability vocabulary above, and why a day is named rather than numbered
- [ADR-019: Store planning preferences as typed columns replaced as a group](../adr/ADR-019-study-goal-planning-preferences.md) — the planning-preference vocabulary above, and why an unset preference is not a default
- [ADR-020: Generate the initial study plan deterministically as a roadmap and a week](../adr/ADR-020-initial-study-plan-generation.md) — the plan vocabulary above, and why a plan item's position is an order rather than a score
- [Domain model](domain-model.md)
- [Domain entities](entities.md)
- [Functional requirements](../requirements/functional.md)
- [Coding standards](../development/coding-standards.md)
