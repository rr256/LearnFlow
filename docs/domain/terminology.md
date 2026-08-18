---
title: LearnFlow Domain Terminology
status: approved
owner: product-and-architecture
last_updated: 2026-08-18
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
  - ../adr/ADR-021-plan-item-completion.md
  - ../adr/ADR-022-plan-adaptation.md
  - ../adr/ADR-023-daily-study-view.md
  - ../adr/ADR-024-plan-item-skipping.md
  - ../adr/ADR-025-learner-postponement.md
  - ../adr/ADR-026-monthly-study-view.md
  - ../adr/ADR-027-plan-feasibility.md
  - ../adr/ADR-028-revision-workflow.md
  - ../adr/ADR-029-progress-overview.md
  - ../adr/ADR-030-learning-stages-by-subject-panel.md
  - ../adr/ADR-031-priority-focus-panel.md
  - ../adr/ADR-032-learning-resource-catalogue.md
  - ../adr/ADR-033-checkpoint-practice-workflow.md
  - ../adr/ADR-034-checkpoint-practice-history.md
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
| **Learning resource** | A learner-owned or curated study reference, recorded as **where the material is** rather than as the material itself. | Includes PDFs, notes, PYQs, formula sheets, and video references. A record carries a title, a *resource type*, where it is — a web link, a *source label* in the learner's own words, or both — and the topics it covers. **Nothing is uploaded or held**, and **no location on the learner's own machine is stored**: a link is an `http` or `https` address, and anything offline is described in words. **Nothing is recommended**: a topic's material is what the learner linked to it, and LearnFlow suggests none of its own. See [ADR-032](../adr/ADR-032-learning-resource-catalogue.md). |
| **Resource type** | What kind of study material a learning resource is: `pdf`, `note`, `pyq`, `formula_sheet`, or `video_reference`. | Stored and sent as the `snake_case` value; the labels a learner reads are *PDF*, *Notes*, *PYQs*, *Formula sheet*, and *Video*. `image` and `attachment` are approved values nothing writes, because each names an uploaded file. |
| **Source label** | Where a learning resource's material is, in the learner's own words. | "Blue binder, chapter 3"; "the lecture series on the external drive". This is what carries material that is not on the web, and it exists so that **no filesystem path has to be stored**. A resource names at least one of a source label and a link. |
| **Resource status** | Whether a learning resource is in the catalogue or put aside: `registered` or `archived`. | Stored and sent as the `snake_case` value. **Nothing deletes a resource**: *put aside* is reversible, and archived material stays in the catalogue while dropping out of the curriculum and revision screens. `processing`, `ready`, and `failed` are approved values nothing writes, because no ingestion exists to move a resource through them. |
| **Learning-resource catalogue** | The screen where a learner records their own study material, corrects it, and puts it aside. | The canonical name for the screen at `/resources`; its UI heading is "Your study material". The **only** place material is written — the curriculum view and the revision screen show a topic's material read-only and link here, the shape the *monthly study view* and the *progress overview* use. It supports **add, edit, and archive**; material put aside is read-only, so a learner puts it back before correcting it. |
| **PYQ** | Previous-year question. | A verified historical exam question; distinguish it from AI-generated practice. |
| **Examination schedule** | The dated calendar an examining body publishes for one cycle of a learning program, such as GATE 2027. | Reference data with a named source, not learner data. Every learner aiming at that cycle reads the same dates. |
| **Examination cycle** | One occurrence of a recurring examination, identified by a label such as `2027`. | A learning program has many cycles over time; each has its own schedule. |
| **Examination period** | One dated span within an examination schedule: registration, late registration, the examination, or the results announcement. | A single-day event starts and ends on the same day. The stored period types are `registration`, `late_registration`, `examination`, and `results`. |
| **Examination window** | The span from the first published sitting day to the last. | Use this, never a single examination date, unless the examining body has published one. Derived from the examination periods; not stored. |
| **Provisional** | A published schedule whose source says the dates are still liable to change. | The honest default before an examining body confirms. Say so wherever the dates are shown. |
| **Confirmed** | A published schedule whose dates the examining body has confirmed. | Set it only on the examining body's word, never on age or proximity. |
| **Learner setup** | The capability by which a learner establishes their profile, active learning program, and study goal before planning begins. | The canonical name for the capability, wherever it is named: requirements, API documentation, endpoint groupings, and UI copy. It is not only a first-time activity — a learner returns to it whenever their goal changes. |
| **Home screen** | The application's landing screen, which shows the learner's saved learner setup — their profile, their study goal, and the published dates of the examination that goal aims at. | Read-only: it reports what is stored and links to *learner setup* to change it. It is not a *dashboard*; see the row below. Its UI heading is "Your study setup". |
| **Progress overview** | The screen gathering where a learner's study stands: **what could use their attention and why**, what their plan covers, what today holds, whether the study time they saved reaches their date, what they have marked, the **learning stage they recorded for each topic, under its subject**, and which topics are ready to review. | The canonical name for the screen, and for the capability [FR-011](../requirements/functional.md#fr-011-progress-overview) describes. A **reading** of contracts that already exist, not a plan and not a new endpoint — PRG-001 stays unbuilt. **It writes nothing at all**: each panel names where its action lives and links to it, as the *monthly study view* does. **It counts nothing of its own** — the only figures on it are ones the API reported; see the rule below the avoid list. That rule is applied panel by panel below the avoid list, hardest on the stages panel, which **lists** a subject's recorded topics and never states how many, and which never orders, groups, or colours them by stage. *Dashboard* is the reserved informal word for this content, never the screen's name, route, or heading. Its UI heading is "Where your study stands". See [ADR-029](../adr/ADR-029-progress-overview.md), [ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md), and [ADR-031](../adr/ADR-031-priority-focus-panel.md) for the *priority focus area* panel it leads with. |
| **Study goal** | The learner's target outcome and deadline. | Aims at an examination cycle, a target completion date, or both — never at neither. |
| **Target date** | A learner's own completion date, for a learner following no published examination. | Not a substitute for an examination window. Leave it empty rather than guessing a paper date. |
| **Availability** | Time the learner can realistically allocate to study. | A planning input, not a measure of commitment or ability. Never presented as a target or a score, and never totalled except by the *plan feasibility* rule, which is the one place that arithmetic belongs. |
| **Availability slot** | The study time available on one day of the week, belonging to one study goal. | A goal holds at most seven, one per day. A slot is a quantity of minutes, not a sitting between two clock times. |
| **Weekly availability** | The whole set of a goal's availability slots. | Saved as a week at a time: the days named become the week, and a day left out is removed. |
| **Day of the week** | One of `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, or `sunday`. | Stored and sent as the `snake_case` name, never as a number. Python, JavaScript, and PostgreSQL disagree about which day is zero, so LearnFlow has no numbering to mis-map. See [ADR-018](../adr/ADR-018-weekly-availability-slots.md). |
| **Kept free** | A day the learner deliberately recorded as having no study time. | Stored as an availability slot of zero minutes. Distinct from a day they have not set, which has no slot at all — the same distinction *Not explored* draws against a topic with no record. |
| **Planning preference** | A choice the learner has made about *how* a study plan should be built, belonging to one study goal. | A planning input beside *weekly availability*, never a measure of anything. A preference the learner has not set is unset, not a default: nothing is invented on their behalf, so a planner meeting an unset preference chooses for itself. See [ADR-019](../adr/ADR-019-study-goal-planning-preferences.md). |
| **Session length** | How long one block of study should be, in minutes. | The learner's preference, stored as `preferred_session_minutes`, from 15 to 480. A **duration**, not a time of day — nothing records when in a day a session falls, for the reason *availability slot* gives. Report it in minutes; a total or an hours figure is planning arithmetic. |
| **Topic order** | Which order a study plan works through the curriculum in. | The learner's preference, stored as `topic_sequencing`: `syllabus_order` follows the syllabus's own order, `prerequisites_first` follows the prerequisite links between topics. Stored and sent as the `snake_case` value; the labels a learner reads are *Syllabus order* and *Prerequisites first*. |
| **Study plan** | A roadmap, monthly plan, weekly plan, or daily plan of recommended work. | Generated against a study goal and current evidence, by deterministic rules rather than by an AI provider. A roadmap and a weekly plan are generated today; see [ADR-020](../adr/ADR-020-initial-study-plan-generation.md). A *daily study view* reads the weekly plan and a *monthly study view* reads both; neither is a plan. |
| **Superseded plan** | A plan a later generation **or adaptation** replaced. | Kept and readable, never deleted: plan history is what makes a change of direction explainable. Its content and reasons keep the wording they were generated with. The one thing that may move on a superseded plan is an item's status, when adaptation marks overdue work *postponed* as it sets the plan aside — a statement about what happened, not a rewriting of what was planned. A learner cannot write into one at all, whatever the status. See [ADR-022](../adr/ADR-022-plan-adaptation.md). |
| **Plan item** | One actionable recommendation in a study plan. | Examples: study, practise, revise, or review mistakes. Its position in the plan is an order, never a score. Its *plan item status* records what became of the work it names. |
| **Plan item status** | What became of the work one plan item names: `planned`, `completed`, `postponed`, or `skipped`. | Stored and sent as the `snake_case` value. It records whether planned **work happened**, never how well a topic is understood — that is a *learning stage*, and nothing derives one from the other. All four are written and all four are things a learner may ask for: `completed`, `skipped`, and `postponed` are the three statements they make about the work, and `planned` takes any of them back. Every move is reversible while the item's plan is active. |
| **Settled item** | A plan item something has already been said about: *completed*, *skipped*, or *postponed*. | The distinction *adaptation* acts on. A settled item is never *overdue* and is never re-marked *postponed*, because doing so would replace a statement with an inference about a date. **`planned` is the only unsettled status** — the one nothing has been said about. See [ADR-025](../adr/ADR-025-learner-postponement.md). |
| **Postponed** | A plan item whose work has not happened yet and is to be placed again on the plan that replaces this one. | **Two writers, one meaning.** The learner writes it through PLN-004 to say *not yet*, and *adaptation* writes it as it supersedes a plan, for work whose day passed with nothing said about it. Either way it is a statement about the **work and its day**, never about the learner's effort or ability. Postponing **moves nothing on its own**: it settles the item, and the work is placed again when the learner adapts. Distinct from *skipped*, which says the work will not happen rather than not yet — a difference in what the record says, not in what the next plan does. Reversible while the plan is active. Nothing records when an item was postponed, or why. See [ADR-025](../adr/ADR-025-learner-postponement.md). |
| **Skipped** | A plan item the learner has said will not happen. | Written by the learner through PLN-004, and reversible while the plan is active. A statement about **that item**, not about the topic: adaptation leaves a skipped item as it is and **plans its topic again**, where a *completed* topic is not planned again. So skipping means "not this time", never "abandon this topic" — the earlier reading, before the lifecycle was designed. Distinct from *postponed*, which says *not yet*; the next plan treats the two identically, so the difference is what the record says. Nothing records when an item was skipped or why, and nothing counts skips. See [ADR-024](../adr/ADR-024-plan-item-skipping.md). |
| **Adaptation** | Rebuilding a goal's active plans around what the learner has and has not done. | The learner asks for it; nothing adapts on its own — completing, skipping, or postponing an item re-plans nothing. It supersedes as a generation does, leaves out topics with completed work, and places again both the work it marks *postponed* and the work the learner did. Deterministic, with no AI provider. Not a re-scoring of the learner and not a judgement about why a day passed. |
| **Plan coverage count** | A count describing how much of the curriculum a plan covers — how many topics it holds, how many remain, how many are not planned again, and how many the learner's saved time reaches. | A description of the **plan**, never a measurement of the learner. Permitted because a plan must be able to explain what it covers and why it is shorter than the one before it. It is never a score, a percentage, a streak, or a total of the learner's time or effort; see the rule below the avoid list. |
| **Daily study view** | The screen showing the work a learner's active weekly plan placed on their own calendar date, alongside work whose day has passed. | A **reading** of the weekly plan, not a plan of its own: no `daily` plan record is written or read, and that plan type stays unwritten. It changes nothing about the plan — saying what became of an item is the only write it offers, and rebuilding the plan stays on the plan screen, where the learner asks for it. "Today" is the learner's date from `learners.timezone`, never the server's. See [ADR-023](../adr/ADR-023-daily-study-view.md). |
| **Monthly study view** | The screen showing where a learner's own calendar month sits in their plan: the days that month already has dated work on, and the roadmap topics their week has not dated. | A **reading** of the roadmap and the weekly plan, not a plan of its own: no `monthly` plan record is written or read, and that plan type stays unwritten. **It writes nothing at all** — marking an item stays in the daily study view and on the plan screen, and rebuilding the plan stays there too. A weekly plan dates seven days, so a month is mostly undated; the screen says so rather than spreading the roadmap across days nothing placed work on, because placing work is planning. The month is the learner's own, from `learners.timezone`, never the server's. See [ADR-026](../adr/ADR-026-monthly-study-view.md). |
| **Plan feasibility** | Whether the study time a learner saved covers the work left on their active plan before their study goal's horizon. | A statement about **the plan and the time**, never about the learner: a week that cannot reach a date is arithmetic, not a verdict on effort. Reported as **counts and durations only** — never a percentage, ratio, or proportion — and with three answers, because *unknown* is honest when a goal aims at no date or no week is saved. A week saved and deliberately kept free is **not** unknown: that is zero minutes. Read live over PLN-006 and never stored, so it moves when the learner's week does. See [ADR-027](../adr/ADR-027-plan-feasibility.md). |
| **Revision status** | What became of one review: `due`, `scheduled`, `completed`, `skipped`, or `postponed`. | Stored and sent as the `snake_case` value. The labels a learner reads are *Ready*, *Scheduled*, **Reviewed**, *Skipped*, and *Postponed* — a review is **reviewed**, not *completed*, because the subject is the review rather than the work. A learner may ask for four of the five, in any direction and reversibly, exactly as for a *plan item status*; `scheduled` is stored-only, because nothing collects the date it needs. A **settled** revision — reviewed, skipped, or postponed — is not offered again on its own. |
| **Revision interval** | How long after finished work a topic comes back for review. | **LearnFlow's own**, never the learner's, and named as such wherever a revision explains itself: 7 days with no learning stage recorded, rising to 21 at *Strong understanding*. A longer interval is **not a better mark** — the stage says what the learner told us, and a topic they are confident with is worth seeing again later. Nothing here ranks two topics, scores a learner, or reorders a *plan*. |
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
| **Revision** | Intentional revisiting of a topic to reinforce retention and address errors. | A *revision record* tracks when it is due and what happened. Created only when the learner asks, from work they have finished — never automatically, and never as a plan item, so it survives the supersede adaptation performs on a plan. It records whether a **review happened**, never that a topic is understood: nothing here writes a learning stage. See [ADR-028](../adr/ADR-028-revision-workflow.md). |
| **Revision due** | A topic currently recommended for revision. | A recommendation, not a failure notice. Its day has arrived or passed and nobody has answered about it — decided by a domain rule and reported by the API, so a screen never decides for itself. Unlike an *overdue* plan item, a revision dated today **is** due: the plan asks for work on a day, and a review is offered from one. Never say a learner is behind on revision, and never count a learner's revisions on a screen or across requests — the one permitted count is REV-004's report of what a single scheduling request left alone, described below. |
| **Checkpoint practice** | The screen where a learner writes their own practice questions, asks for a quiz on the topics they choose, answers it, and reads what became of each question. | The canonical name for the screen at `/practice`, and for this capability in prose and UI copy. Named for what a learner does there. **Writing lives there alone**; `/practice/quizzes/{id}` is where a quiz is answered, `/practice/attempts/{id}` is a read-only result, and `/practice/history` is the *checkpoint practice history* defined below. Do not call it a *test*, a *mock*, or an *exam* — none of those is what it is, and each imports a verdict. |
| **Checkpoint quiz** | A short, topic-focused practice assessment. | Used to gather evidence after study or revision. Assembled **deterministically from the learner's own questions**, and it asks *every* one of them for the topics chosen: LearnFlow selects none and leaves none out, because choosing which few to ask is a ranking. *Short* is therefore the learner's decision, not the product's. |
| **Question / assessment item** | One answerable prompt within a quiz or question bank. | May be AI-generated or from a verified source; today it is **written by the learner**, and no question content ships with LearnFlow. **Never edited** — a learner corrects one by setting it aside and writing another, because attempts already marked against it reference it, and rewriting a prompt would rewrite a result the learner has already read. |
| **Quiz attempt** | A learner's submitted response to a checkpoint quiz. | Records what became of **each question** — correct, not correct, or *unanswered* — with the expected answer and the explanation. It records **no score, no mark, and no total**; see the rule below. An unanswered question is not a wrong one, which is why the three outcomes are kept apart. |
| **Checkpoint practice history** | The record of the checkpoint quizzes a learner has taken, newest first, with what became of each question. | The canonical name for the screen at `/practice/history` and for this reading in prose and UI copy. **A list, never a summary**: it states no score, no mark, no percentage, no count of quizzes taken or questions answered, no streak, and no average, and it sets **no attempt against another** — the rule below forbids each by name, and a history is where they are most tempting. Read live over QZ-006 and stored nowhere. Shown **a page at a time**, which is not a *cap*: the order is the API's own, newest first, and every attempt stays reachable, where capping would mean choosing which few to show. Do not number the pages — a page count is a count of the learner's quizzes with an extra step. Two words as a noun — *the checkpoint practice history* — and hyphenated only as a compound modifier, as in *the checkpoint-practice history screen*, which is why ADR-034's title carries the hyphen. See [ADR-034](../adr/ADR-034-checkpoint-practice-history.md). |
| **External test result** | A learner-entered result from an assessment completed outside LearnFlow. | Canonical term for the whole recorded result. May reference Testbook, Made Easy, or another provider; it is not an integration. |
| **Topic performance evidence** | Topic-specific marks, attempts, or mistakes recorded from an external test result. | Canonical term for the topic-level detail inside an external test result; it belongs to one external test result and one topic. Checkpoint quiz outcomes are never topic performance evidence. Only create it when the external test report actually provides topic-level information. |
| **Mistake evidence** | A recorded error or learning gap. | Initial categories: concept gap, calculation error, careless error, time-management issue. |
| **Priority focus area** | Something LearnFlow already has a record of that could use the learner's attention now. | Prefer this in the UI over “weak topic.” **Built as a gathering, never as a ranking**, and drawn only from facts a backend rule already decided: a plan item whose day has passed with nothing said about it, a review the backend reports as due, and a saved week that PLN-006 says does not reach the horizon or cannot be assessed. **The recorded learning stage is not one of them** — selecting some of the five stages as priorities would rank them against each other, which nothing in LearnFlow does. Nothing is ordered by importance, numbered, capped, scored, or counted, and no priority is ever stated of a *subject*: a subject-level claim needs either a count or a comparison against its neighbours. The earlier reading — "a topic or action currently likely to benefit the learner **most**" — is superseded: *most* is a superlative over topics, and no such comparison is made. See [ADR-031](../adr/ADR-031-priority-focus-panel.md). |
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
| Complete | Material completed; plan item completed | Clarify whether material or a planned task was completed. A count of topics with completed planned work is a *plan coverage count*, not a claim that the topics themselves are complete. |
| A learner who is behind; falling behind; an overdue learner | An **overdue item**; work whose day has passed; postponed work | A day passing is a fact about a date, not a verdict on a person. Say an *item* is overdue, never that the learner is behind: LearnFlow marks the item postponed and places the work again, and forms no view about why the day passed. *Overdue* is correct of an item and wrong of a learner. |
| Putting it off; delaying; procrastinating; a learner who keeps postponing | A **postponed item**; work to be placed again | Postponing settles one plan item and says nothing about the learner's effort or ability. Wording that reads as a character description forms a view the product refuses, and nothing counts postponements anyway. |
| Abandoned topic; dropped topic; giving up on a topic | A **skipped item** | Skipping settles one plan item, not a topic, and that item's topic is planned again. Wording that says the learner gave something up overstates what was stored and forms a view about why. Say the item was skipped. |
| Skip reason; postponement reason; why an item was skipped or postponed | Nothing — it is not recorded | No reason is collected or stored for either. Asking would invite the product to form a view about the answer, which [FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) refuses. |
| Progress percentage; completion rate; topics done out of total; streak | A plan coverage count, stated as a count | See the rule below. A plan may say how many topics it covers and how many are not planned again; nothing converts that into a rate, a percentage, or a running score. |
| Exam date; examination date | Examination window; examination period | A body that publishes several sitting days has not named the learner's day. A single date presents a guess as a deadline. |
| Exam; GATE date | Examination cycle; examination schedule | Keeps platform-core language reusable across learning programs. |
| Onboarding | Learner setup | Use **learner setup** for the capability. **Onboarding** is permitted for one narrower thing only: the first-time UI flow a learner walks through before they have a profile or a goal. It never names the capability, its endpoints, or the ongoing ability to change a goal — a learner who edits an established goal is not being onboarded. |
| Dashboard (as a screen's name) | Progress overview; home screen | **The screen the word was reserved for now exists**, at `/progress`, and its canonical name is *progress overview* — FR-011's own title, and what a learner does there rather than what it looks like. *Dashboard* stays the reserved informal word for that content and names nothing: not the route, not the heading, not a component. It is still wrong for the landing screen, which is the **home screen** and shows the saved *learner setup*; calling that one a dashboard would make one word mean two things. **The overview does not deliver all of FR-011**: upcoming work and revisions due are shown, and so are the recorded learning stages gathered by subject; *priority focus areas* are now shown **for the evidence LearnFlow stores**, while quiz and external-test history are not, and PRG-001 is still unbuilt. See [ADR-029](../adr/ADR-029-progress-overview.md), [ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md), and [ADR-031](../adr/ADR-031-priority-focus-panel.md). |
| Weekly study hours; total available time | Weekly availability; the availability of one day | A total is planning arithmetic, and it invites a judgement about whether a week is *enough*. FR-003's planner is what should form that view, with the trade-offs visible — and since [ADR-027](../adr/ADR-027-plan-feasibility.md) it does, in the domain rule behind *plan feasibility*. **That rule is the one place a week is totalled and the one place that judgement is made.** Nowhere else adds a week up: not a goal response, not a plan, and not a screen of its own accord. The feasibility panel shows the durations that rule returned; it computes none of them. |
| Quiz score; marks; "you got 3 of 5"; accuracy | What became of each question — *correct*, *not the expected answer*, *unanswered* | A quiz result states per-question outcomes and no total. `quiz_attempts.score` and the marks columns are not created, so there is nothing to add up. See the rule below and [ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md). |
| Plan priority (as a rank); most important topic | Plan item order; where an item falls in the plan | `plan_items.priority` is a position counted from 1, not a score. A topic later in a plan is later, not weaker — the same distinction the learning stages draw. Nothing in LearnFlow ranks two topics against each other. |
| Study pace; intensity; study style | Planning preference; session length; topic order | *Pace* and *intensity* sound like settings but define nothing a planner can act on, and they invite a judgement about how hard a learner is working. Name the specific choice being made. |
| Default session length; recommended topic order | An unset planning preference | A preference the learner has not set has no value, and presenting one as a default would report a decision they did not make. Say it is unset, and let the planner choose visibly — which it does, naming the choice as its own. |
| Time slot; study session (for availability) | Availability slot | An availability slot is a quantity of minutes on a day, not a booking between two clock times. Nothing stores a time of day. |
| Recommended resource; suggested material; best book for a topic | The learner's material for a topic | LearnFlow holds no study material and has assessed none, so it recommends none. A topic's material is what the learner linked to it, in the order the API returned; a topic with nothing linked shows nothing rather than an invented suggestion. A curated list is a ranking whether or not it is presented as one. |
| Upload; attach a file; a resource's contents | Register a resource; where the material is | A *learning resource* is a record of **where material is**, never the material: nothing is uploaded, downloaded, extracted, or indexed. Wording that implies LearnFlow holds a copy describes a capability that does not exist. |
| Delete a resource; remove material | Put material aside; archive | **Nothing implemented today deletes a learner's record**, and the catalogue is no exception: putting material aside is reversible and it stays in the catalogue, which is what *superseded plan* and *skipped* each establish for their own records. RES-005 and EXT-005 are catalogued `DELETE` endpoints that nothing implements; say *put aside* of a resource unless one of them is built. |
| Test integration | Manual external test result entry | The MVP does not connect to third-party test platforms. |
| AI memory | Learner progress, resource retrieval, or conversation context | Store durable facts in the application/database, not in model memory. |
| GATE topic | Topic in the GATE CSE learning program | Keeps platform-core language reusable. |

### Plan coverage counts are not learner scores

Adaptation gave LearnFlow its first numbers that describe a learner's situation rather than the
curriculum, so the line between the two is drawn here rather than left to each change to rediscover.

**Permitted — a plan describing its own coverage.** A plan may state how many topics it holds, how
many remain, and how many are not planned again because their work is done. These are facts about
*the plan*: they explain why an adapted plan is shorter than the one it replaced, which is what makes
adaptation legible rather than mysterious. `completed_topic_count` and `remaining_topic_count` on
PLN-005 are these, and so is `item_count`. **`coverable_topic_count` on PLN-006 is one too**: it
describes how far the time the learner saved reaches, which is a fact about their week and the
plan rather than about them. It is stated **beside** `remaining_topic_count` as a second count and
never as one over the other — the rule below applies to it exactly as to the others.

**Permitted — a scheduling request describing what it just did.**
`already_scheduled_topic_count` on REV-004 is how many finished topics **that request** passed over
because they already had a review waiting or one the learner had settled. It is a neutral fact about
**one scheduling request**, and it exists so that a run which writes nothing says why instead of
appearing to fail.

Its permission is deliberately narrow. It is **never learner progress**, and never a ratio, a
percentage, a rate, or a score. It must not be presented as how much revision a learner has done,
compared against how many topics they have finished, accumulated across requests, or shown on a
screen as a standing figure — it describes an action the product just took, not the learner and not
their history. **Nothing counts a learner's revisions**, and no revision count appears in the
interface at all.

**Forbidden — a number that rates the learner.** No percentage complete, no completion rate, no
"14 of 60 done", no streak, no score, no total of a day, a week, or a plan. These turn a description
of work into a measurement of a person, and every one of them invites the judgement
[FR-005](../requirements/functional.md#fr-005-topic-progress-and-learning-evidence) refuses and the
*weak topic* row above avoids.

**A screen renders the figures it was given and derives none.** The rules above govern what may be
*computed*, and the *progress overview* is where that distinction had to be settled, because
gathering a learner's situation is exactly where a screen is tempted to add things up. It renders a
plan's `item_count` and the counts and durations PLN-006 returned, and calculates nothing itself — no
completion count, no skip or postponement tally, and no revision count, each forbidden by name above.
What replaces them is a **list**: naming the topics a learner marked, with the plan and the reason,
says more than a number and cannot be compared against last week, a target, or another learner, which
is the third test. See [ADR-029](../adr/ADR-029-progress-overview.md).

The same rule decides what the overview's **learning stages by subject** may say. A count beside a
subject name — "Operating Systems, 4 topics recorded" — is forbidden for the same reason: its subject
is the learner, it would read as zero for a learner who has recorded nothing, and it invites a
comparison against the subject below it. So a subject **lists** its recorded topics and states no
figure, and a subject holding none is left out rather than shown as empty, because "none yet" beside a
name is one word from the count. Nor is the panel ever ordered, grouped, or coloured **by stage**: a
learner may move to any of the five from any of them, so a scale would rank two topics against each
other, which nothing in LearnFlow does. See
[ADR-030](../adr/ADR-030-learning-stages-by-subject-panel.md).

The rule met its hardest case in **checkpoint practice**, where a score is what everyone expects. A
quiz result states what became of each question and **no total at all**: no mark, no percentage, and
no "3 of 5", which is the shape forbidden by name above. The three tests decide it — the subject of
"you got 3 of 5" is the learner rather than the work, the figure is meaningless for an attempt nobody
has made, and it invites a comparison with last week's attempt. So `quiz_attempts.score`,
`quiz_attempts.max_score`, `quiz_questions.max_marks`, and `quiz_attempt_answers.awarded_marks` are
**not created at all**, rather than created and left unread: a column that exists is a column
something will eventually total. This is the one place where this document and
[schema.md](../database/schema.md) disagreed, and
[ADR-033](../adr/ADR-033-checkpoint-practice-workflow.md) resolves it here. **Nothing counts a
learner's quizzes**, no quiz count appears in the interface, and no attempt is set against another.

That last clause is tested hardest by the **checkpoint practice history**, where several attempts
sit on one screen and every obvious addition to it is forbidden above: how many quizzes have been
taken, how many questions went as expected in each, a run of good ones, a comparison with last
week. The history states **none of them**. It says what each attempt covered, when it happened,
and what became of each question in words — a list, which is what replaced a number on the
progress overview for the same reason. Paging it is not capping it: the order is the API's own and
every attempt stays reachable, where choosing which few to show would be the ranking
[ADR-031](../adr/ADR-031-priority-focus-panel.md) refuses. The pages are **not numbered**, because
a page count is a count of the learner's quizzes with an extra step, and `pagination.total` — which
*is* that count — is never read rather than merely never rendered. See
[ADR-034](../adr/ADR-034-checkpoint-practice-history.md).

The rule is tested again by the overview's **priority focus area** panel, whose whole subject is
what needs attention. It states **no figure at all**: no tally of what is outstanding, no
count of reviews owed — forbidden by name above — and no percentage, fraction, streak, or bar. It
also **ranks nothing**, which is the second half of the same discipline: its groups sit in a fixed
presentation order that orders nothing, no entry is numbered, no group is styled as more urgent than
another, and the list is never capped, because choosing which few to show *is* a ranking. A recorded
*learning stage* is deliberately not a signal there, for the reason the paragraph above gives. See
[ADR-031](../adr/ADR-031-priority-focus-panel.md).

Three tests distinguish them:

1. **What is the subject?** "This plan covers 55 topics" describes a plan. "You have completed 8%"
   describes a learner.
2. **Would it still be true of a plan nobody had acted on?** A coverage count of a freshly generated
   plan is meaningful; a completion rate of one is zero, which says nothing.
3. **Does it invite a comparison?** Against last week, against a target, against another learner — if
   so it is a score, whatever it is called.

A plan-coverage count is always reported **as a count**, never as a ratio or a proportion, because a
ratio has a denominator and a denominator invites the comparison the third test rules out.

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
- Name a screen for what a learner does there, not for a UI genre. *Home screen* says where it sits
  and *progress overview* says what a learner reads there; *dashboard* would say what each looks
  like, and that word names no screen, as the row above records.
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
- [ADR-021: Mark a plan item completed as a reversible statement about work, not about the learner](../adr/ADR-021-plan-item-completion.md) — the wording a completed plan item uses, and why it is a statement about work rather than about the learner
- [ADR-022: Adapt a study plan by rebuilding it around what happened](../adr/ADR-022-plan-adaptation.md) — the plan a learner has rebuilt around what happened, and the `postponed` state adaptation writes
- [ADR-023: Show today's work as a reading of the weekly plan, not a daily plan](../adr/ADR-023-daily-study-view.md) — the *daily study view* above, and the screen where an item is overdue and a learner never is
- [ADR-024: Let a learner skip a plan item, settling the item without retiring the topic](../adr/ADR-024-plan-item-skipping.md) — *skipped* and *settled item* above, and why skipping an item does not abandon a topic
- [ADR-025: Let a learner postpone a plan item, settling it while the work waits for the next adaptation](../adr/ADR-025-learner-postponement.md) — *postponed* above, its two writers, and why it settles an item without moving it
- [ADR-026: Show the month as a reading of the roadmap and the week, not a monthly plan](../adr/ADR-026-monthly-study-view.md) — the *monthly study view* above, and why a month mostly without dates says so rather than being filled in
- [ADR-027: Report whether the saved week reaches the horizon, as a read-only planning rule](../adr/ADR-027-plan-feasibility.md) — *plan feasibility* above, the one place a week is totalled, and why the answer is counts rather than a ratio
- [ADR-033: Assemble checkpoint practice from the learner's own questions, and report outcomes rather than a score](../adr/ADR-033-checkpoint-practice-workflow.md) — the quiz vocabulary above, and why a result states outcomes rather than a score
- [ADR-034: Show the checkpoint-practice history as a paged reading of stored attempts, counting nothing](../adr/ADR-034-checkpoint-practice-history.md) — the history vocabulary above, why paging is not capping, and why the pages are not numbered
- [ADR-029: Show the progress overview as a reading of what is stored, counting nothing of its own](../adr/ADR-029-progress-overview.md) — *progress overview* above, the screen the word *dashboard* was reserved for, and why it lists what a learner marked rather than counting it
- [ADR-030: Gather the recorded learning stages by subject, listing them rather than counting them](../adr/ADR-030-learning-stages-by-subject-panel.md) — the stages panel the overview gained, and why a subject may not carry a count or an order over the five stages
- [ADR-031: Draw priority focus from facts backend rules already decided, ranking nothing](../adr/ADR-031-priority-focus-panel.md) — *priority focus area* above, the three stored facts it is gathered from, and why the recorded stage is not one of them
- [ADR-032: Catalogue learner-owned study material as metadata, linked to topics](../adr/ADR-032-learning-resource-catalogue.md) — *learning resource*, *resource type*, *source label*, and *resource status* above, and why nothing is recommended, uploaded, or deleted
- [Domain model](domain-model.md)
- [Domain entities](entities.md)
- [Functional requirements](../requirements/functional.md)
- [Coding standards](../development/coding-standards.md)
