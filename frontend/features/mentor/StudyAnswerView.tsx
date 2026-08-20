import Link from "next/link";

import styles from "@/features/mentor/StudyAnswerView.module.css";
import type { StudyAnswer } from "@/types/study-answer";
import { isUngrounded } from "@/types/study-answer";

interface StudyAnswerViewProps {
  /** What MNT-001 answered with. */
  answer: StudyAnswer;
}

/**
 * One answer, with the passages it was built from beneath it.
 *
 * **The answer and its grounds are always shown together.** There is no branch
 * that renders prose alone: the passages come from the same result, so a learner
 * can read what a model said and what they themselves wrote, and judge one
 * against the other. That is the whole point of a grounded answer, and it is why
 * the citations are a property of the result rather than something this
 * component fetches.
 *
 * **Both are rendered as plain text.** Nothing here parses the answer as HTML or
 * Markdown and nothing reaches `dangerouslySetInnerHTML` — React escapes them
 * and CSS `white-space: pre-wrap` keeps the line breaks. That applies with more
 * force to the answer than to a passage: a passage came from the learner, while
 * an answer came from a model, and a model's output is text arriving over a
 * network like any other.
 *
 * **Nothing is parsed out of the prose.** The citation list is what the backend
 * retrieved and sent; this reads no marker, number, or source name out of the
 * answer, so an answer cannot cite a note that was never consulted.
 *
 * **Nothing is counted, scored, or ranked.** No confidence, no relevance, no
 * "3 sources", and no figure beside a learner's own writing.
 */
export function StudyAnswerView({ answer }: StudyAnswerViewProps) {
  return (
    <section aria-labelledby="study-answer" className={styles.result}>
      <h2 id="study-answer">
        {answer.outcome === "answered"
          ? `About ${answer.topic_name}`
          : `Nothing answered for ${answer.topic_name}`}
      </h2>
      <p className={styles.asked}>You asked: {answer.question}</p>

      {answer.answer === null ? (
        <NoAnswer answer={answer} />
      ) : (
        <>
          <p className={styles.answer}>{answer.answer}</p>
          <p className={styles.caution}>
            Written by a local AI model from the passages below, and nothing else. Check it
            against them — a model can still be wrong about what it was given.
          </p>
        </>
      )}

      {answer.passages.length > 0 ? (
        <>
          <h3 className={styles.groundsHeading}>
            {answer.answer === null ? "What was found in your notes" : "From your own notes"}
          </h3>
          <ul className={styles.items}>
            {answer.passages.map((passage) => (
              <li className={styles.item} key={`${passage.note_id}-${passage.passage.slice(0, 24)}`}>
                <p className={styles.passage}>{passage.passage}</p>
                <p className={styles.source}>
                  <span className={styles.note}>{passage.note_title}</span> on{" "}
                  <Link href="/resources">{passage.resource_title}</Link>{" "}
                  <span className={styles.kind}>({passage.resource_type})</span>
                </p>
              </li>
            ))}
          </ul>
          <p className={styles.footnote}>
            Each passage is an extract of what you wrote, character for character. Open the
            material on <Link href="/resources">your study material</Link> to read a note in full.
          </p>
        </>
      ) : null}
    </section>
  );
}

/**
 * Why there is no answer, said plainly.
 *
 * Six situations reach this, in two groups that mean quite different things. The
 * **ungrounded** three mean no model was asked at all — LearnFlow had nothing of
 * the learner's to answer from and declined to invent something. The
 * **provider** three mean it was asked and could not answer, and the passages
 * are still shown above.
 *
 * They are kept apart because they ask for different next steps: write a note,
 * or start a model. An outcome this build does not recognise is reported
 * honestly rather than guessed at.
 */
function NoAnswer({ answer }: { answer: StudyAnswer }) {
  const guidance = {
    no_linked_material: (
      <>
        You have not linked any material to {answer.topic_name} yet, so there was nothing to
        answer from. Add a piece on <Link href="/resources">your study material</Link>, link it to
        this topic, and write a note on it.
      </>
    ),
    no_active_notes: (
      <>
        You have material linked to {answer.topic_name}, but no notes on it yet. Open it on{" "}
        <Link href="/resources">your study material</Link> and write what you want to keep. A note
        you have put aside is not read.
      </>
    ),
    no_matching_passage: (
      <>
        Your notes on {answer.topic_name} do not mention this in words, so there was nothing to
        ground an answer in. Try another topic, or write a note covering it.
      </>
    ),
    provider_unavailable: (
      <>
        The AI model could not be reached, so your question was not answered. It runs on this
        computer — start Ollama, or check that the model named in your configuration is installed,
        and ask again.
      </>
    ),
    provider_timed_out: (
      <>
        The AI model did not answer in time. It runs on this computer, so this usually means it is
        working slowly rather than broken. Ask again, or try a shorter question.
      </>
    ),
    provider_unusable_reply: (
      <>
        The AI model replied with nothing usable. Ask again, or try wording the question
        differently.
      </>
    ),
  }[answer.outcome];

  return (
    <>
      <p className={styles.empty}>
        {guidance ?? (
          <>
            The answer reported <code>{answer.outcome}</code>, which this screen does not have
            wording for. Your notes are unchanged.
          </>
        )}
      </p>
      {isUngrounded(answer.outcome) ? (
        <p className={styles.declined}>
          No AI model was asked. LearnFlow answers from your own notes, so with nothing of yours
          to draw on it says so rather than answering from what a model happens to know.
        </p>
      ) : null}
    </>
  );
}
