import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";

import {
  searchLibrary,
  useAddFromCommunity,
  useCreateItem,
  useReference,
  useSaveChapters,
  useSaveLessons,
  type LibraryItem,
  type SearchResult,
  type SearchResults,
} from "../../api/parent";
import { ErrorLine, TextField } from "../ui/Fields";
import { Modal, Steps } from "../ui/Modal";
import { ReadinessList } from "../ui/Checklist";
import { BookCover } from "./BookCover";
import { KindFields, draftToCreate, emptyDraft, type Draft } from "./KindFields";
import { ChapterEditor, LessonEditor } from "./StructureEditors";

type Step = "find" | "basics" | "kind" | "details" | "structure" | "done";

const LOOKUP_SOURCES = new Set(["book_cache", "open_library", "google_books"]);

/** Which step comes after the details, for this kind of book. */
function hasStructure(draft: Draft): boolean {
  if (draft.kind === "textbook") return !draft.for_parent;
  return draft.kind === "reading_book" || draft.kind === "workbook";
}

function structureLabel(kind: string): string {
  return kind === "textbook" ? "Lessons" : "Chapters";
}

/** What's missing on the details step, so "Save" can explain instead of failing. */
function missingDetails(draft: Draft): string[] {
  const missing: string[] = [];
  const need = (ok: unknown, label: string) => !ok && missing.push(label);
  if (draft.kind === "reading_book") {
    need(draft.author.trim(), "the author");
    need(draft.total_pages, "the total pages");
  } else if (draft.kind === "textbook") {
    need(draft.publisher.trim(), "the publisher");
    need(draft.edition.trim(), "the edition or year");
    need(draft.subject_code, "the subject");
    need(draft.grade, "the grade");
    need(draft.total_pages, "the total pages");
  } else if (draft.kind === "workbook") {
    need(draft.subject_code, "the subject");
    need(draft.grade, "the grade");
    need(draft.total_pages, "the total pages");
  } else if (draft.kind === "online_program") {
    need(draft.website_url.trim(), "the website link");
    need(draft.subject_code, "the subject");
    need(draft.grade, "the grade");
    need(draft.measure, "lessons or minutes");
    if (draft.measure === "lessons") need(draft.lesson_count, "the number of lessons");
    if (draft.measure === "minutes") need(draft.minutes_per_session, "minutes a session");
    need(draft.days_per_week, "days a week");
  }
  return missing;
}

function SearchStep({
  onPickLookup,
  onManual,
  onAdopted,
  onOpenItem,
}: {
  onPickLookup: (result: SearchResult) => void;
  onManual: (title: string) => void;
  onAdopted: (item: LibraryItem) => void;
  onOpenItem: (id: number) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const adopt = useAddFromCommunity();

  const search = async (event: FormEvent) => {
    event.preventDefault();
    if (query.trim().length < 2) return;
    setSearching(true);
    setError(null);
    try {
      setResults(await searchLibrary(query.trim()));
    } catch (problem) {
      setError(problem);
    } finally {
      setSearching(false);
    }
  };

  const groups = results
    ? [
        {
          title: "In the Curiculy catalog: ready to use",
          rows: results.results.filter((result) => result.source === "community"),
        },
        { title: "Already in your library", rows: results.results.filter((result) => result.source === "library") },
        {
          title: "Book matches: start from these details",
          rows: results.results.filter((result) => LOOKUP_SOURCES.has(result.source)),
        },
      ].filter((group) => group.rows.length > 0)
    : [];

  return (
    <div className="stack-lg">
      <p className="step-lede">
        Search first: someone may have entered it already. Type an ISBN (the number by the barcode), a title, an author
        or a series.
      </p>
      <form className="search-row" onSubmit={search} role="search">
        <label className="sr-only" htmlFor="library-search">
          ISBN, title, author or series
        </label>
        <input
          id="library-search"
          className="input"
          type="search"
          value={query}
          data-autofocus=""
          placeholder="Saxon Math 5/4, or 978-1-59166-…"
          onChange={(event) => setQuery(event.target.value)}
        />
        <button type="submit" className="btn btn-primary" disabled={searching || query.trim().length < 2}>
          {searching ? "Searching…" : "Search"}
        </button>
      </form>
      <ErrorLine error={error ?? adopt.error} />
      {results?.notice ? <p className="notice">{results.notice}</p> : null}
      {groups.map((group) => (
        <section className="results-group" key={group.title}>
          <h3>{group.title}</h3>
          {group.rows.map((result, index) => (
            <div className="result" key={`${result.source}-${result.isbn ?? result.title}-${index}`}>
              <BookCover
                small
                url={result.cover_url}
                title={result.title}
                kindLabel={result.guessed_kind_label}
                subjectCode={null}
                kind={result.guessed_kind}
              />
              <div>
                <p className="result-title">{result.title}</p>
                <p className="result-meta">
                  {[(result.authors ?? []).join(", "), result.publisher, result.year, result.total_pages ? `${result.total_pages} pages` : null]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <p className="result-meta">
                  {result.source === "community"
                    ? `${result.guessed_kind_label} · ${result.detail ?? ""}`
                    : `Looks like: ${result.guessed_kind_label}`}
                </p>
              </div>
              {result.source === "community" ? (
                <button
                  type="button"
                  className="btn btn-primary btn-small"
                  disabled={adopt.isPending}
                  onClick={() => adopt.mutate(result.catalog_entry_id as number, { onSuccess: onAdopted })}
                >
                  Add to my library
                </button>
              ) : result.source === "library" ? (
                <button type="button" className="btn btn-small" onClick={() => onOpenItem(result.library_item_id as number)}>
                  Open it
                </button>
              ) : (
                <button type="button" className="btn btn-small" onClick={() => onPickLookup(result)}>
                  Use these details
                </button>
              )}
            </div>
          ))}
        </section>
      ))}
      <div className="card row-between">
        <div>
          <p className="card-title">Can't find it?</p>
          <p className="card-meta">Add it yourself. It takes a minute or two, and helps the next family.</p>
        </div>
        <button type="button" className="btn" onClick={() => onManual(results && !/^[\d\s-]+$/.test(query) ? query.trim() : "")}>
          Add it yourself
        </button>
      </div>
    </div>
  );
}

/**
 * Adding to the Library, one step at a time: find it (the catalog first), the
 * basics, "What is this?", the questions for that kind, its chapters or
 * lessons, and what's left before it can be scheduled.
 */
export function AddWalkthrough({ onClose, onOpenItem }: { onClose: () => void; onOpenItem: (id: number) => void }) {
  const navigate = useNavigate();
  const reference = useReference();
  const [step, setStep] = useState<Step>("find");
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [guess, setGuess] = useState<string | null>(null);
  const [item, setItem] = useState<LibraryItem | null>(null);
  const [detailsProblem, setDetailsProblem] = useState("");
  const [fromCatalog, setFromCatalog] = useState(false);
  const create = useCreateItem();
  const chapters = useSaveChapters(item?.id ?? 0);
  const lessons = useSaveLessons(item?.id ?? 0);

  const change = (patch: Partial<Draft>) => setDraft((current) => ({ ...current, ...patch }));
  const kinds = reference.data?.library_kinds ?? [];
  const kindLabel = kinds.find((kind) => kind.code === draft.kind)?.label ?? "it";

  const labels = ["Find it", "The basics", "What is this?", "Details", ...(hasStructure(draft) ? [structureLabel(draft.kind)] : []), "Done"];
  const order: Step[] = ["find", "basics", "kind", "details", ...(hasStructure(draft) ? (["structure"] as Step[]) : []), "done"];
  const current = Math.max(0, order.indexOf(step));

  const titles: Record<Step, string> = {
    find: "Add to your library",
    basics: "The basics",
    kind: "What is this?",
    details: `About this ${kindLabel.toLowerCase()}`,
    structure: draft.kind === "textbook" ? "The lesson list" : "Chapters",
    done: fromCatalog ? "Added from the catalog" : "Added to your library",
  };

  const finish = (saved: LibraryItem) => {
    setItem(saved);
    setStep("done");
  };

  const saveDetails = () => {
    const missing = missingDetails(draft);
    if (missing.length) {
      setDetailsProblem(
        `Still needed before it can be scheduled: ${missing.join(", ")}. You can save it now and finish later, or fill them in.`,
      );
    } else {
      setDetailsProblem("");
    }
    create.mutate(draftToCreate(draft), {
      onSuccess: (created) => {
        setItem(created);
        setStep(hasStructure(draft) ? "structure" : "done");
      },
    });
  };

  let body: ReactNode = null;
  let footer: ReactNode = null;

  if (step === "find") {
    body = (
      <SearchStep
        onOpenItem={(id) => {
          onClose();
          onOpenItem(id);
        }}
        onAdopted={(adopted) => {
          setItem(adopted);
          setFromCatalog(true);
          setDraft((current) => ({ ...current, kind: adopted.kind, for_parent: adopted.for_parent }));
          setStep("done");
        }}
        onManual={(title) => {
          setDraft({ ...emptyDraft(), title });
          setGuess(null);
          setStep("basics");
        }}
        onPickLookup={(result) => {
          setDraft({
            ...emptyDraft(),
            title: result.subtitle ? `${result.title}: ${result.subtitle}` : result.title,
            author: (result.authors ?? []).join(", "),
            publisher: result.publisher ?? "",
            isbn: result.isbn ?? "",
            total_pages: result.total_pages ?? null,
            cover_url: result.cover_url?.startsWith("http") ? result.cover_url : "",
            kind: result.guessed_kind,
          });
          setGuess(result.guessed_kind);
          setStep("basics");
        }}
      />
    );
  }

  if (step === "basics") {
    body = (
      <div className="stack-lg">
        <p className="step-lede">Start with what's on the cover. You'll say what kind of book it is next.</p>
        <div className="form-grid">
          <TextField label="Title" required wide autoFocus value={draft.title} onChange={(value) => change({ title: value })} />
          <TextField label="Author" value={draft.author} onChange={(value) => change({ author: value })} />
          <TextField label="Publisher" value={draft.publisher} onChange={(value) => change({ publisher: value })} />
          <TextField
            label="ISBN"
            value={draft.isbn}
            onChange={(value) => change({ isbn: value })}
            hint="The number by the barcode. It helps other families find the same edition."
          />
        </div>
      </div>
    );
    footer = (
      <>
        <button type="button" className="btn btn-quiet" onClick={() => setStep("find")}>
          Back to search
        </button>
        <button type="button" className="btn btn-primary" disabled={!draft.title.trim()} onClick={() => setStep("kind")}>
          Next: what is this?
        </button>
      </>
    );
  }

  if (step === "kind") {
    body = (
      <div className="stack-lg">
        <p className="step-lede">
          Each kind asks different questions, so Curiculy can schedule it the right way. {guess ? "We made a guess; change it if it's wrong." : ""}
        </p>
        <fieldset className="choice-cards">
          <legend className="sr-only">What kind of book is {draft.title}?</legend>
          {kinds.map((kind) => (
            <label className="choice-card" key={kind.code}>
              <input
                type="radio"
                name="kind"
                value={kind.code}
                checked={draft.kind === kind.code}
                onChange={() => change({ kind: kind.code })}
              />
              <span className="choice-title">{kind.label}</span>
              <span className="choice-hint">{kind.hint}</span>
              {guess === kind.code ? <span className="badge badge-info choice-guess">Our guess</span> : null}
            </label>
          ))}
        </fieldset>
      </div>
    );
    footer = (
      <>
        <button type="button" className="btn btn-quiet" onClick={() => setStep("basics")}>
          Back
        </button>
        <button type="button" className="btn btn-primary" disabled={!draft.kind} onClick={() => setStep("details")}>
          Next: the details
        </button>
      </>
    );
  }

  if (step === "details") {
    body = (
      <div className="stack-lg">
        <p className="step-lede">
          Fields marked * are what Curiculy needs to put {draft.title} on the calendar. You can save it now and fill in
          the rest later; it just can't be scheduled until then.
        </p>
        <KindFields draft={draft} onChange={change} reference={reference.data} />
        {detailsProblem ? <p className="notice notice-warn">{detailsProblem}</p> : null}
        <ErrorLine error={create.error} />
      </div>
    );
    footer = (
      <>
        <button type="button" className="btn btn-quiet" onClick={() => setStep("kind")}>
          Back
        </button>
        <button type="button" className="btn btn-primary" disabled={create.isPending} onClick={saveDetails}>
          {create.isPending ? "Saving…" : hasStructure(draft) ? `Save, then add ${structureLabel(draft.kind).toLowerCase()}` : "Save to my library"}
        </button>
      </>
    );
  }

  if (step === "structure" && item) {
    body =
      item.kind === "textbook" ? (
        <LessonEditor
          initial={[]}
          saving={lessons.isPending}
          error={lessons.error}
          saveLabel="Save and finish"
          onSave={(rows) => lessons.mutate(rows, { onSuccess: finish })}
        />
      ) : (
        <ChapterEditor
          initial={[]}
          required={item.kind === "workbook"}
          saving={chapters.isPending}
          error={chapters.error}
          saveLabel="Save and finish"
          onSave={(rows) => chapters.mutate(rows, { onSuccess: finish })}
        />
      );
    footer = (
      <>
        <span />
        <button type="button" className="btn btn-quiet" onClick={() => setStep("done")}>
          Skip for now
        </button>
      </>
    );
  }

  if (step === "done" && item) {
    const plannable = item.kind === "textbook" && !item.for_parent;
    body = (
      <div className="stack-lg">
        <div className="row">
          <BookCover
            small
            url={item.cover.url}
            title={item.title}
            kindLabel={item.kind_label}
            subjectCode={item.subject_code}
            kind={item.kind}
          />
          <div>
            <p className="card-title">{item.title}</p>
            <p className="card-meta">
              {item.kind_label}
              {item.subject_name ? ` · ${item.subject_name}` : ""}
              {item.grade ? ` · Grade ${item.grade}` : ""}
            </p>
          </div>
        </div>
        <section className="stack" aria-label="Ready to schedule?">
          <h3 className="section-title">Ready to schedule?</h3>
          <ReadinessList readiness={item.readiness} />
        </section>
        {item.community ? <p className="notice">{item.community.label}</p> : null}
        {plannable ? (
          <p className="notice notice-success">
            A textbook is the heart of a curriculum. Next, plan it: add the workbooks, websites and books that go with
            it, then put it on the calendar.
          </p>
        ) : null}
      </div>
    );
    footer = (
      <>
        <button
          type="button"
          className="btn btn-quiet"
          onClick={() => {
            setDraft(emptyDraft());
            setItem(null);
            setFromCatalog(false);
            setStep("find");
          }}
        >
          Add another
        </button>
        <div className="row">
          <button
            type="button"
            className="btn"
            onClick={() => {
              onClose();
              onOpenItem(item.id);
            }}
          >
            Open it
          </button>
          {plannable ? (
            <button type="button" className="btn btn-primary" onClick={() => navigate(`/planner/new?textbook=${item.id}`)}>
              Plan a curriculum with it
            </button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={onClose}>
              Done
            </button>
          )}
        </div>
      </>
    );
  }

  return (
    <Modal title={titles[step]} onClose={onClose} steps={<Steps labels={labels} current={current} />} wide={step === "structure"} footer={footer}>
      {body}
    </Modal>
  );
}
