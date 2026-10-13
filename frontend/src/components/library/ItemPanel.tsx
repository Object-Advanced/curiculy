import { useEffect, useId, useState } from "react";
import { Link, useNavigate } from "react-router";

import {
  useDeleteItem,
  useLibraryItem,
  useReference,
  useRemoveCover,
  useSaveChapters,
  useSaveLessons,
  useUpdateItem,
  useUploadCover,
  type LibraryItem,
} from "../../api/parent";
import { ReadinessList } from "../ui/Checklist";
import { ErrorLine, TextField } from "../ui/Fields";
import { Modal } from "../ui/Modal";
import { BookCover } from "./BookCover";
import { KindFields, draftFromItem, draftToFields, type Draft } from "./KindFields";
import { ChapterEditor, LessonEditor } from "./StructureEditors";

type Tab = "details" | "structure" | "cover";

function CoverSection({ item }: { item: LibraryItem }) {
  const upload = useUploadCover(item.id);
  const remove = useRemoveCover(item.id);
  const inputId = useId();
  return (
    <div className="stack-lg">
      <div className="row">
        <BookCover url={item.cover.url} title={item.title} kindLabel={item.kind_label} subjectCode={item.subject_code} kind={item.kind} />
        <div className="stack">
          <p className="step-lede">
            {item.cover.source === "upload"
              ? item.cover.review === "approved"
                ? "Your uploaded cover. It's approved, so other families see it in the catalog too."
                : item.cover.review === "rejected"
                  ? "Your uploaded cover. It wasn't added to the catalog, but it still shows on your shelf."
                  : "Your uploaded cover. It shows on your shelf now; an admin reviews it before other families see it."
              : item.cover.source === "lookup"
                ? "This cover came from the book lookup."
                : item.cover.source === "community"
                  ? "This cover came from the Curiculy catalog."
                  : "No cover yet, so your shelf shows one made from the title."}
          </p>
          <p className="field-hint">
            Upload a real cover image (a PNG or JPG of the published cover, from the publisher's website for example),
            not a photo of your copy. Up to 5 MB.
          </p>
        </div>
      </div>
      <div className="row">
        <label className="btn" htmlFor={inputId}>
          {upload.isPending ? "Uploading…" : "Upload a cover image"}
        </label>
        <input
          id={inputId}
          className="sr-only"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) upload.mutate(file);
            event.target.value = "";
          }}
        />
        {item.cover.source === "upload" ? (
          <button type="button" className="btn btn-quiet" disabled={remove.isPending} onClick={() => remove.mutate()}>
            Remove the uploaded cover
          </button>
        ) : null}
      </div>
      <ErrorLine error={upload.error ?? remove.error} />
    </div>
  );
}

function DetailsSection({ item }: { item: LibraryItem }) {
  const reference = useReference();
  const update = useUpdateItem(item.id);
  const [draft, setDraft] = useState<Draft>(() => draftFromItem(item));
  const [saved, setSaved] = useState(false);
  const change = (patch: Partial<Draft>) => {
    setSaved(false);
    setDraft((current) => ({ ...current, ...patch }));
  };
  return (
    <form
      className="stack-lg"
      onSubmit={(event) => {
        event.preventDefault();
        update.mutate(draftToFields(draft), { onSuccess: () => setSaved(true) });
      }}
    >
      <div className="form-grid">
        <TextField label="Title" required wide value={draft.title} onChange={(value) => change({ title: value })} />
        {item.kind === "textbook" || item.kind === "workbook" ? (
          <TextField label="Author" value={draft.author} onChange={(value) => change({ author: value })} />
        ) : null}
        {item.kind === "reading_book" ? (
          <TextField label="Publisher" value={draft.publisher} onChange={(value) => change({ publisher: value })} />
        ) : null}
        {item.kind !== "online_program" ? (
          <TextField label="ISBN" value={draft.isbn} onChange={(value) => change({ isbn: value })} />
        ) : null}
      </div>
      <KindFields draft={draft} onChange={change} reference={reference.data} />
      <div className="row">
        <button type="submit" className="btn btn-primary" disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save changes"}
        </button>
        {saved ? (
          <span className="muted small" role="status">
            Saved.
          </span>
        ) : null}
      </div>
      <ErrorLine error={update.error} />
    </form>
  );
}

function StructureSection({ item }: { item: LibraryItem }) {
  const chapters = useSaveChapters(item.id);
  const lessons = useSaveLessons(item.id);
  if (item.kind === "textbook") {
    if (item.for_parent) {
      return <p className="notice">A teacher's edition is for you, so it doesn't need a lesson list of its own.</p>;
    }
    return (
      <LessonEditor
        key={item.lessons.length}
        initial={item.lessons.map((lesson) => ({
          number: lesson.number ?? null,
          name: lesson.name ?? "",
          type: lesson.type as "lesson",
          start_page: lesson.start_page ?? null,
          end_page: lesson.end_page ?? null,
        }))}
        saving={lessons.isPending}
        error={lessons.error}
        onSave={(rows) => lessons.mutate(rows)}
      />
    );
  }
  return (
    <ChapterEditor
      key={item.chapters.length}
      initial={item.chapters.map((chapter) => ({ name: chapter.name, start_page: chapter.start_page }))}
      required={item.kind === "workbook"}
      saving={chapters.isPending}
      error={chapters.error}
      onSave={(rows) => chapters.mutate(rows)}
    />
  );
}

/** One library item: what's left before it can be scheduled, and every part of it to edit. */
export function ItemPanel({ itemId, onClose }: { itemId: number; onClose: () => void }) {
  const navigate = useNavigate();
  const query = useLibraryItem(itemId);
  const remove = useDeleteItem();
  const [tab, setTab] = useState<Tab>("details");
  const [confirming, setConfirming] = useState(false);
  const item = query.data;

  useEffect(() => {
    if (item && !item.ready && item.readiness.missing.some((m) => ["lessons", "lesson_names", "lesson_pages", "chapters"].includes(m.field))) {
      setTab("structure");
    }
    // Only when it first opens: start where the work is.
  }, [item?.id]);

  if (!item) {
    return (
      <Modal title="Library" onClose={onClose}>
        {query.isError ? <ErrorLine error={query.error} /> : <p className="muted">Loading…</p>}
      </Modal>
    );
  }

  const curricula = item.curriculum_ids ?? [];
  const hasStructure = item.kind !== "online_program";
  const structureName = item.kind === "textbook" ? "Lesson list" : "Chapters";
  const plannable = item.kind === "textbook" && !item.for_parent;

  return (
    <Modal
      title={item.title}
      onClose={onClose}
      wide
      footer={
        <>
          {confirming ? (
            <div className="row">
              <span className="small">Delete {item.title} from your library? Lessons already on the calendar stay.</span>
              <button
                type="button"
                className="btn btn-danger btn-small"
                onClick={() => remove.mutate(item.id, { onSuccess: onClose })}
                disabled={remove.isPending}
              >
                Yes, delete it
              </button>
              <button type="button" className="btn btn-quiet btn-small" onClick={() => setConfirming(false)}>
                Keep it
              </button>
            </div>
          ) : (
            <button type="button" className="btn btn-danger btn-small" onClick={() => setConfirming(true)}>
              Delete
            </button>
          )}
          {plannable ? (
            <button type="button" className="btn btn-primary" onClick={() => navigate(`/planner/new?textbook=${item.id}`)}>
              Plan a curriculum with it
            </button>
          ) : null}
        </>
      }
    >
      <div className="row">
        <BookCover small url={item.cover.url} title={item.title} kindLabel={item.kind_label} subjectCode={item.subject_code} kind={item.kind} />
        <div className="stack">
          <p className="card-meta">
            {item.kind_label}
            {item.subject_name ? ` · ${item.subject_name}` : ""}
            {item.grade ? ` · Grade ${item.grade}` : ""}
            {item.author ? ` · ${item.author}` : ""}
          </p>
          {item.community ? <p className="field-hint">{item.community.label}</p> : null}
          {curricula.length ? (
            <p className="field-hint">
              Part of {curricula.length === 1 ? "a curriculum" : `${curricula.length} curricula`}:{" "}
              {curricula.map((id, index) => (
                <span key={id}>
                  {index ? ", " : ""}
                  <Link to={`/planner/${id}`}>open {curricula.length === 1 ? "it" : index + 1}</Link>
                </span>
              ))}
            </p>
          ) : null}
        </div>
      </div>
      <section className="stack" aria-label="Ready to schedule?">
        <h3 className="section-title">Ready to schedule?</h3>
        <ReadinessList readiness={item.readiness} />
      </section>
      <div className="chips" role="tablist" aria-label="Edit">
        {(["details", ...(hasStructure ? ["structure"] : []), "cover"] as Tab[]).map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            className="chip"
            aria-selected={tab === name}
            aria-pressed={tab === name}
            onClick={() => setTab(name)}
          >
            {name === "details" ? "Details" : name === "structure" ? structureName : "Cover"}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === "details" ? <DetailsSection key={item.id} item={item} /> : null}
        {tab === "structure" ? <StructureSection item={item} /> : null}
        {tab === "cover" ? <CoverSection item={item} /> : null}
      </div>
      <ErrorLine error={remove.error} />
    </Modal>
  );
}
