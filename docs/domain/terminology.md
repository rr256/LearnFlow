---
title: LearnFlow Domain Terminology
status: approved
owner: product-and-architecture
last_updated: 2026-08-01
related:
  - ../00-project-context.md
  - domain-model.md
  - entities.md
  - ../adr/ADR-013-examination-schedule-and-study-goal.md
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
| **Study goal** | The learner's target outcome and deadline. | Aims at an examination cycle, a target completion date, or both — never at neither. |
| **Target date** | A learner's own completion date, for a learner following no published examination. | Not a substitute for an examination window. Leave it empty rather than guessing a paper date. |
| **Availability** | Time the learner can realistically allocate to study. | A planning input, not a measure of commitment or ability. |
| **Study plan** | A roadmap, monthly plan, weekly plan, or daily plan of recommended work. | Generated against a study goal and current evidence. |
| **Plan item** | One actionable recommendation in a study plan. | Examples: study, practise, revise, or review mistakes. |
| **Study activity** | A record of actual study, practice, or revision work completed by the learner. | May record duration and related resources/topics. |
| **Learner topic progress** | The learner-specific state and evidence for one topic. | Combines several signals; it is not a single permanent score. |
| **Material completed** | The learner has completed the planned material for a topic. | Does not mean mastery or exam readiness. |
| **Learning stage** | A supportive, learner-visible summary of current understanding. | Use the approved stage labels below. |
| **Not explored** | No meaningful work or evidence is recorded for the topic. | Neutral starting state. |
| **Building foundation** | The learner should focus on concepts and basic study. | Use a constructive next action. |
| **Developing confidence** | The learner has partial understanding and needs focused practice. | Do not label this as weak. |
| **Practice-ready** | The learner is ready for more topic-focused questions. | Not a guarantee of exam performance. |
| **Strong understanding** | Recent evidence indicates consistent understanding; scheduled revision is still needed. | Do not call this permanent mastery. |
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

## Related Documents

- [Project context](../00-project-context.md)
- [ADR-013: Model an examination period as a published window of reference data](../adr/ADR-013-examination-schedule-and-study-goal.md) — the examination vocabulary above
- [Domain model](domain-model.md)
- [Domain entities](entities.md)
- [Functional requirements](../requirements/functional.md)
- [Coding standards](../development/coding-standards.md)
