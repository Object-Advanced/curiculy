import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useReadingList, type ReadingEntry } from "../api/parent";
import { useStudents } from "../api/queries";
import { BookCover } from "../components/library/BookCover";
import { AddReadingModal, EditReadingModal, useReadingStep } from "../components/reading/ReadingForms";
import { ErrorLine } from "../components/ui/Fields";
import { shortDate } from "../lib/dates";

const SECTIONS: { status: ReadingEntry["status"]; title: string; empty: string }[] = [
  { status: "reading", title: "Reading now", empty: "Nothing right now." },
  { status: "up_next", title: "Up next", empty: "Nothing waiting." },
  { status: "finished", title: "Finished", empty: "None finished yet this year." },
];

function when(entry: ReadingEntry): string | null {
  if (entry.status === "finished" && entry.finished_on) {
    const started = entry.started_on && entry.started_on !== entry.finished_on ? `${shortDate(entry.started_on)} to ` : "";
    return `Read ${started}${shortDate(entry.finished_on)}`;
  }
  if (entry.status === "reading" && entry.started_on) return `Started ${shortDate(entry.started_on)}`;
  return null;
}

function Entry({ entry, onEdit }: { entry: ReadingEntry; onEdit: () => void }) {
  const { step, pending } = useReadingStep();
  const book = entry.book;
  return (
    <li className="card reading-entry">
      <BookCover small url={book.cover.url} title={book.title} kindLabel={book.kind_label} subjectCode={book.subject_code} kind={book.kind} />
      <div className="stack">
        <div>
          <h3 className="card-title">{book.title}</h3>
          <p className="card-meta">
            {[book.author, `Counts toward ${entry.counts_toward_name}`].filter(Boolean).join(" · ")}
          </p>
        </div>
        {when(entry) ? <p className="small">{when(entry)}</p> : null}
        {entry.scheduled ? (
          <p className="small muted">
            On the calendar: {entry.lessons_done} of {entry.lessons_total} reading{entry.lessons_total === 1 ? "" : "s"} done
          </p>
        ) : null}
        <div className="row">
          {entry.status !== "finished" ? (
            <button type="button" className="btn btn-small" disabled={pending} onClick={() => step(entry)}>
              {entry.status === "up_next" ? "Started it" : "Finished it"}
            </button>
          ) : null}
          <button type="button" className="btn btn-quiet btn-small" onClick={onEdit} aria-label={`Change ${book.title}`}>
            Change
          </button>
        </div>
      </div>
    </li>
  );
}

/**
 * Each child's reading list for the school year: reading now, up next, and
 * finished. Books scheduled on the calendar join by themselves and move along
 * as their reading is checked off. `?child=<id>` picks the child.
 */
export function ReadingPage() {
  const [params, setParams] = useSearchParams();
  const students = useStudents(true);
  const kids = students.data ?? [];
  const asked = Number(params.get("child"));
  const child = kids.find((kid) => kid.id === asked) ?? kids[0] ?? null;
  const list = useReadingList(child?.id ?? null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<ReadingEntry | null>(null);

  useEffect(() => {
    document.title = "Reading lists · Curiculy";
  }, []);

  const entries = list.data ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Reading lists</h1>
          <p className="page-lede">
            Every book each child reads this year, with when they started and finished. Books you schedule move along by
            themselves as their reading is checked off. The list goes into their records and portfolio.
          </p>
        </div>
        <div className="page-actions">
          {child ? (
            <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
              Add a book
            </button>
          ) : null}
        </div>
      </div>

      {students.isError ? <ErrorLine error={students.error} /> : null}
      {students.isSuccess && kids.length === 0 ? (
        <p className="notice">Add your children first (Kids, in the menu above). Then each one gets a reading list.</p>
      ) : null}

      {kids.length > 1 ? (
        <div className="chips" aria-label="Whose list">
          {kids.map((kid) => (
            <button
              key={kid.id}
              type="button"
              className="chip"
              aria-pressed={kid.id === child?.id}
              onClick={() => setParams({ child: String(kid.id) }, { replace: true })}
            >
              {kid.name}
            </button>
          ))}
        </div>
      ) : null}

      {list.isError ? <ErrorLine error={list.error} /> : null}
      {child && list.isPending ? <p className="muted">Loading {child.name}'s list…</p> : null}
      {child && list.isSuccess && entries.length === 0 ? (
        <section className="card empty-shelf" aria-label="An empty reading list">
          <h2 className="section-title">Nothing on {child.name}'s list yet</h2>
          <p className="step-lede">
            Add a book they're reading or have read this year. To give it daily reading on the calendar, open it in your{" "}
            <Link to="/library">Library</Link> and choose Schedule it: it joins this list by itself.
          </p>
          <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
            Add a book
          </button>
        </section>
      ) : null}

      {child && entries.length > 0
        ? SECTIONS.map((section) => {
            const shown = entries.filter((entry) => entry.status === section.status);
            return (
              <section className="stack" key={section.status} aria-label={section.title}>
                <h2 className="section-title">
                  {section.title} <span className="chip-count">{shown.length}</span>
                </h2>
                {shown.length ? (
                  <ul className="reading-list">
                    {shown.map((entry) => (
                      <Entry key={entry.id} entry={entry} onEdit={() => setEditing(entry)} />
                    ))}
                  </ul>
                ) : (
                  <p className="muted small">{section.empty}</p>
                )}
              </section>
            );
          })
        : null}

      {adding && child ? (
        <AddReadingModal
          studentId={child.id}
          studentName={child.name}
          onList={entries.map((entry) => entry.book.id)}
          onClose={() => setAdding(false)}
        />
      ) : null}
      {editing ? <EditReadingModal entry={editing} onClose={() => setEditing(null)} /> : null}
    </>
  );
}
