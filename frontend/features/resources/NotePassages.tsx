import Link from "next/link";

import styles from "@/features/resources/NotePassages.module.css";
import { resourceTypeLabel } from "@/types/resource";
import type { TopicNoteSearch } from "@/types/note-search";

interface NotePassagesProps {
  result: TopicNoteSearch;
}

/**
 * The passages one search found, in the order the API returned them.
 *
 * **The text is rendered as text.** Every passage goes through JSX, which
 * escapes it — nothing here calls `dangerouslySetInnerHTML`, parses Markdown, or
 * interprets the content, so a note containing `vector<int>` or a tag is
 * something the learner reads. `white-space: pre-wrap` preserves their own line
 * breaks rather than inserting markup.
 *
 * **A passage is an exact substring of the note**, cut in the application rather
 * than rendered by the database, so nothing on the way here can drop or rewrite
 * a character. See ADR-038.
 *
 * **Nothing is ranked, scored, or counted.** No relevance figure exists in the
 * contract to render, no passage is numbered, and no total says how many notes
 * the learner has — a figure beside their own writing would measure them, which
 * is the line docs/domain/terminology.md draws. The order is the API's own.
 *
 * **Nothing is generated.** Every word on this screen is either the learner's or
 * a label; LearnFlow answers nothing, summarises nothing, and suggests nothing.
 *
 * An empty answer says **which** of three things happened, because each asks the
 * learner to do something different.
 */
export function NotePassages({ result }: NotePassagesProps) {
  if (result.outcome !== "found") {
    return <NothingFound result={result} />;
  }

  return (
    <section aria-labelledby="passages" className={styles.results}>
      <h2 id="passages">
        From your notes on {result.topic_name}
      </h2>
      <p className={styles.lead}>
        Your own words, from the material you linked to this topic. Nothing here was written or
        rewritten by LearnFlow — each passage is copied out of your note exactly as you typed it.
        A long note is shown in part; open it to read the rest.
      </p>

      <ul className={styles.items}>
        {result.passages.map((passage) => (
          <li className={styles.item} key={`${passage.note_id}-${passage.resource_id}`}>
            {/*
              `pre-wrap` in CSS rather than generated markup: the learner's line
              breaks survive, and the text is escaped by React before it reaches
              here, so nothing it contains can execute.
            */}
            <p className={styles.passage}>{passage.passage}</p>

            <p className={styles.source}>
              <span className={styles.note}>{passage.note_title}</span>
              {" — from "}
              <span className={styles.kind}>{resourceTypeLabel(passage.resource_type)}</span>{" "}
              {passage.resource_title}
            </p>
            <p className={styles.context}>
              {passage.subject_name} · {passage.topic_name}
            </p>
          </li>
        ))}
      </ul>

      <p className={styles.footnote}>
        Notes are read and written on <Link href="/resources">your study material</Link>.
      </p>
    </section>
  );
}

/**
 * Why a search found nothing, said plainly.
 *
 * Three situations reach this and they mean different things: link some
 * material, write a note, or try another topic. Collapsing them into "nothing
 * found" would hide which one applies. An outcome this build does not recognise
 * is reported honestly rather than guessed at.
 */
function NothingFound({ result }: { result: TopicNoteSearch }) {
  const guidance = {
    no_linked_material: (
      <>
        You have not linked any material to {result.topic_name} yet. Add a piece on{" "}
        <Link href="/resources">your study material</Link> and link it to this topic, then write
        a note on it.
      </>
    ),
    no_active_notes: (
      <>
        You have material linked to {result.topic_name}, but no notes on it yet. Open it on{" "}
        <Link href="/resources">your study material</Link> and write what you want to keep. A note
        you have put aside is not searched.
      </>
    ),
    no_matching_passage: (
      <>
        Your notes on {result.topic_name} do not mention it in words, so there is no passage to
        show. That is not a judgement about the notes — try another topic, or open the material on{" "}
        <Link href="/resources">your study material</Link> to read them in full.
      </>
    ),
  }[result.outcome];

  return (
    <section aria-labelledby="nothing-found" className={styles.results}>
      <h2 id="nothing-found">Nothing to show for {result.topic_name}</h2>
      <p className={styles.empty}>
        {guidance ?? (
          <>
            The search reported <code>{result.outcome}</code>, which this screen does not have
            wording for. Your notes are unchanged.
          </>
        )}
      </p>
    </section>
  );
}
