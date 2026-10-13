import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { useLibrary, useReference, type LibrarySummary } from "../api/parent";
import { AddWalkthrough } from "../components/library/AddWalkthrough";
import { BookCover } from "../components/library/BookCover";
import { ItemPanel } from "../components/library/ItemPanel";
import { ErrorLine } from "../components/ui/Fields";

const FILTERS: { code: string; label: string }[] = [
  { code: "", label: "All" },
  { code: "reading_book", label: "Books" },
  { code: "textbook", label: "Textbooks" },
  { code: "workbook", label: "Workbooks" },
  { code: "online_program", label: "Online sites" },
];

function status(item: LibrarySummary): { text: string; className: string } {
  if (item.ready) return { text: "Ready to schedule", className: "badge badge-ready" };
  const count = item.missing_count + item.problems_count;
  return { text: `${count} thing${count === 1 ? "" : "s"} to finish`, className: "badge badge-missing" };
}

function EmptyShelf({ onAdd }: { onAdd: () => void }) {
  const reference = useReference();
  return (
    <section className="card empty-shelf" aria-label="Your library is empty">
      <h2 className="section-title">Your shelf is empty, for now</h2>
      <p className="step-lede">
        The Library holds everything you teach or read from. Each kind is set up a little differently, so Curiculy can
        schedule it the right way:
      </p>
      <ul className="explain">
        {(reference.data?.library_kinds ?? []).map((kind) => (
          <li key={kind.code}>
            <strong>{kind.label}</strong>
            <span className="muted small">{kind.hint}</span>
          </li>
        ))}
      </ul>
      <button type="button" className="btn btn-primary" onClick={onAdd}>
        Add your first book
      </button>
    </section>
  );
}

/**
 * The Library: every book, textbook, workbook and online site the family
 * teaches or reads from, on one shelf. `?add=1` opens the adding walkthrough;
 * `?item=<id>` opens one item (the planner links here to finish something).
 */
export function LibraryPage() {
  const [params, setParams] = useSearchParams();
  const library = useLibrary();
  const [filter, setFilter] = useState("");
  const adding = params.get("add") === "1";
  const openId = params.get("item") ? Number(params.get("item")) : null;

  useEffect(() => {
    document.title = "Library · Curiculy";
  }, []);

  const setParam = (name: string, value: string | null) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value === null) next.delete(name);
        else next.set(name, value);
        return next;
      },
      { replace: true },
    );

  const items = library.data ?? [];
  const shown = filter ? items.filter((item) => item.kind === filter) : items;
  const welcome = params.get("welcome") === "1";

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Library</h1>
          <p className="page-lede">
            Every book you teach or read from, on one shelf: books, textbooks, workbooks and online sites. Plan how they
            fit together in the <Link to="/planner">Curriculum planner</Link>.
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="btn btn-primary" onClick={() => setParam("add", "1")}>
            Add to library
          </button>
        </div>
      </div>

      {welcome ? (
        <div className="notice notice-success">
          <p>
            <strong>Welcome!</strong> Start by adding what you teach from. Search the Curiculy catalog first: if another
            family already entered your book, it's ready in seconds.
          </p>
        </div>
      ) : null}

      {items.length > 0 ? (
        <div className="chips" aria-label="Show">
          {FILTERS.map((option) => {
            const count = option.code ? items.filter((item) => item.kind === option.code).length : items.length;
            return (
              <button
                key={option.code || "all"}
                type="button"
                className="chip"
                aria-pressed={filter === option.code}
                onClick={() => setFilter(option.code)}
              >
                {option.label} <span className="chip-count">{count}</span>
              </button>
            );
          })}
        </div>
      ) : null}

      {library.isError ? <ErrorLine error={library.error} /> : null}
      {library.isPending ? <p className="muted">Loading your library…</p> : null}
      {library.isSuccess && items.length === 0 ? <EmptyShelf onAdd={() => setParam("add", "1")} /> : null}
      {library.isSuccess && items.length > 0 && shown.length === 0 ? (
        <p className="muted">Nothing of this kind yet.</p>
      ) : null}

      {shown.length > 0 ? (
        <ul className="shelf" aria-label="Your shelf">
          {shown.map((item) => {
            const badge = status(item);
            return (
              <li className="book" key={item.id}>
                <button type="button" className="book-button" onClick={() => setParam("item", String(item.id))}>
                  <span className="book-stand">
                    <BookCover
                      url={item.cover.url}
                      title={item.title}
                      kindLabel={item.kind_label}
                      subjectCode={item.subject_code}
                      kind={item.kind}
                    />
                  </span>
                  <span className="book-title">{item.title}</span>
                  <span className="book-meta">
                    {item.kind_label}
                    {item.grade ? ` · Grade ${item.grade}` : ""}
                  </span>
                  {item.subject_name ? <span className="book-meta">{item.subject_name}</span> : null}
                  <span className={badge.className}>{badge.text}</span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}

      {adding ? (
        <AddWalkthrough onClose={() => setParam("add", null)} onOpenItem={(id) => setParams({ item: String(id) }, { replace: true })} />
      ) : null}
      {openId !== null && !adding ? <ItemPanel itemId={openId} onClose={() => setParam("item", null)} /> : null}
    </>
  );
}
