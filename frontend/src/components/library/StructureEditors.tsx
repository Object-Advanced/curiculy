import { useId, useState } from "react";

import { readPagePhoto, type ChapterWrite, type LessonWrite } from "../../api/parent";
import {
  numberedLessons,
  parseChapters,
  parseLessons,
  type ChapterDraft,
  type LessonDraft,
  type LessonType,
} from "../../lib/structure";
import { ErrorLine, TextArea } from "../ui/Fields";

const LESSON_TYPES: { value: LessonType; label: string }[] = [
  { value: "lesson", label: "Lesson" },
  { value: "test", label: "Test" },
  { value: "quiz", label: "Quiz" },
  { value: "review", label: "Review" },
  { value: "project", label: "Project" },
];

const toNumber = (value: string) => (value === "" ? null : Number(value));

function PasteBox({
  label,
  hint,
  placeholder,
  onRead,
}: {
  label: string;
  hint: string;
  placeholder: string;
  onRead: (text: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [message, setMessage] = useState("");
  const [photoNote, setPhotoNote] = useState("");
  const [reading, setReading] = useState(false);
  const fileId = useId();

  const readPhoto = async (file: File) => {
    setReading(true);
    setMessage("");
    try {
      const result = await readPagePhoto(file);
      setValue(result.text);
      setPhotoNote(result.message);
      setOpen(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "That photo couldn't be read.");
    } finally {
      setReading(false);
    }
  };

  if (!open) {
    return (
      <span className="row">
        <button
          type="button"
          className="btn btn-small"
          onClick={() => {
            setPhotoNote("");
            setOpen(true);
          }}
        >
          {label}
        </button>
        <label className="btn btn-small" htmlFor={fileId}>
          {reading ? "Reading the photo…" : "Read a photo of the page"}
        </label>
        <input
          id={fileId}
          className="sr-only"
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void readPhoto(file);
            event.target.value = "";
          }}
        />
        {message ? (
          <span className="field-hint" role="status">
            {message}
          </span>
        ) : null}
      </span>
    );
  }
  return (
    <div className="card stack">
      {photoNote ? (
        <p className="notice" role="status">
          {photoNote}
        </p>
      ) : null}
      <TextArea label={label} hint={hint} value={value} onChange={setValue} placeholder={placeholder} />
      <div className="row">
        <button
          type="button"
          className="btn btn-small btn-primary"
          onClick={() => {
            setMessage(onRead(value));
            setValue("");
            setOpen(false);
          }}
        >
          Add these
        </button>
        <button type="button" className="btn btn-small btn-quiet" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  );
}

/** Chapters: each one's name and the page it starts on. */
export function ChapterEditor({
  initial,
  required,
  saving,
  error,
  onSave,
  saveLabel = "Save chapters",
}: {
  initial: ChapterDraft[];
  required: boolean;
  saving: boolean;
  error: unknown;
  onSave: (chapters: ChapterWrite[]) => void;
  saveLabel?: string;
}) {
  const [rows, setRows] = useState<ChapterDraft[]>(initial.length ? initial : [{ name: "", start_page: null }]);
  const [problem, setProblem] = useState("");
  const caption = useId();
  const update = (index: number, patch: Partial<ChapterDraft>) =>
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  const save = () => {
    const filled = rows.filter((row) => row.name.trim() || row.start_page !== null);
    if (filled.some((row) => !row.name.trim() || row.start_page === null)) {
      setProblem("Every chapter needs a name and the page it starts on.");
      return;
    }
    if (required && filled.length === 0) {
      setProblem("Add at least one chapter.");
      return;
    }
    setProblem("");
    onSave(filled.map((row) => ({ name: row.name.trim(), start_page: row.start_page as number })));
  };

  return (
    <div className="editor">
      <p className="step-lede" id={caption}>
        {required
          ? "Add each chapter's name and the page it starts on. Curiculy keeps each day's pages inside one chapter, and re-plans cleanly when you miss a day."
          : "Optional: with chapters, you can schedule this book a chapter at a time (\"ch. 3–4\") instead of by pages."}
      </p>
      <div className="row">
        <PasteBox
          label="Paste the contents page"
          hint="One chapter per line, with its start page at the end: “Fractions, 62”."
          placeholder={"Addition, 5\nSubtraction, 31\nFractions, 62"}
          onRead={(text) => {
            const { rows: read, skipped } = parseChapters(text);
            setRows((current) => [...current.filter((row) => row.name.trim() || row.start_page !== null), ...read]);
            return `Added ${read.length} chapter${read.length === 1 ? "" : "s"}.${skipped ? ` ${skipped} line${skipped === 1 ? "" : "s"} had no page number and were skipped.` : ""}`;
          }}
        />
      </div>
      <div className="editor-scroll">
        <table className="editor-table" aria-describedby={caption}>
          <thead>
            <tr>
              <th scope="col">Chapter name</th>
              <th scope="col">Starts on page</th>
              <th scope="col">
                <span className="sr-only">Remove</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                <td>
                  <input
                    className="input input-small"
                    aria-label={`Chapter ${index + 1} name`}
                    value={row.name}
                    onChange={(event) => update(index, { name: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    className="input input-small num-input"
                    type="number"
                    min={1}
                    aria-label={`Chapter ${index + 1} start page`}
                    value={row.start_page ?? ""}
                    onChange={(event) => update(index, { start_page: toNumber(event.target.value) })}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="btn btn-quiet btn-small"
                    aria-label={`Remove chapter ${index + 1}`}
                    onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="row-between">
        <button type="button" className="btn btn-small" onClick={() => setRows((current) => [...current, { name: "", start_page: null }])}>
          Add a chapter
        </button>
        <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : saveLabel}
        </button>
      </div>
      {problem ? <p className="field-error">{problem}</p> : null}
      <ErrorLine error={error} />
    </div>
  );
}

/** A textbook's full lesson list: number, name, type, and first and last page. */
export function LessonEditor({
  initial,
  saving,
  error,
  onSave,
  saveLabel = "Save the lesson list",
}: {
  initial: LessonDraft[];
  saving: boolean;
  error: unknown;
  onSave: (lessons: LessonWrite[]) => void;
  saveLabel?: string;
}) {
  const [rows, setRows] = useState<LessonDraft[]>(initial);
  const [count, setCount] = useState<number | null>(null);
  const [problem, setProblem] = useState("");
  const caption = useId();
  const countId = useId();
  const update = (index: number, patch: Partial<LessonDraft>) =>
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  const nextNumber = () => {
    const numbers = rows.map((row) => row.number).filter((n): n is number => n !== null);
    return numbers.length ? Math.max(...numbers) + 1 : 1;
  };
  const withPages = rows.filter((row) => row.start_page !== null && row.end_page !== null).length;

  const save = () => {
    if (rows.some((row) => row.number === null)) {
      setProblem("Every lesson needs a number.");
      return;
    }
    setProblem("");
    onSave(
      rows.map((row) => ({
        number: row.number,
        name: row.name.trim() || null,
        type: row.type,
        start_page: row.start_page,
        end_page: row.end_page,
        minutes: row.minutes ?? null,
      })),
    );
  };

  return (
    <div className="editor">
      <p className="step-lede" id={caption}>
        Every lesson, in order: its number, its name, and its first and last page (quizzes and tests too), plus how many minutes it takes if you know. The calendar
        places one lesson each school day, keeps tests on their own day, and can only catch up properly after a missed
        day when every lesson is listed. You can save part of it now and finish later.
      </p>
      <div className="row">
        <label className="field-label" htmlFor={countId}>
          Make numbered lessons
        </label>
        <input
          id={countId}
          className="input input-small num-input"
          type="number"
          min={1}
          max={1000}
          placeholder="170"
          value={count ?? ""}
          onChange={(event) => setCount(toNumber(event.target.value))}
        />
        <button
          type="button"
          className="btn btn-small"
          disabled={!count}
          onClick={() => {
            if (!count) return;
            setRows((current) => [...current, ...numberedLessons(count, nextNumber())]);
            setCount(null);
          }}
        >
          Make them
        </button>
        <PasteBox
          label="Paste a lesson list"
          hint="One lesson per line, like “12 The Lost Dog 45-49” or “Test 2, 54-55”. Numbers and pages are read for you."
          placeholder={"1 Adding 1-4\n2 Subtracting 5-8\nTest 1, 9-10"}
          onRead={(text) => {
            const { rows: read, skipped } = parseLessons(text, nextNumber());
            setRows((current) => [...current, ...read]);
            return `Added ${read.length} lesson${read.length === 1 ? "" : "s"}.${skipped ? ` Skipped ${skipped} empty line${skipped === 1 ? "" : "s"}.` : ""}`;
          }}
        />
      </div>
      <p className="field-hint" role="status">
        {rows.length} lesson{rows.length === 1 ? "" : "s"}, {withPages} with pages.
      </p>
      {rows.length ? (
        <div className="editor-scroll">
          <table className="editor-table" aria-describedby={caption}>
            <thead>
              <tr>
                <th scope="col">No.</th>
                <th scope="col">Name</th>
                <th scope="col">Type</th>
                <th scope="col">First page</th>
                <th scope="col">Last page</th>
                <th scope="col">Minutes</th>
                <th scope="col">
                  <span className="sr-only">Remove</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const label = `Lesson ${row.number ?? index + 1}`;
                return (
                  <tr key={index}>
                    <td>
                      <input
                        className="input input-small num-input"
                        type="number"
                        min={1}
                        aria-label={`${label} number`}
                        value={row.number ?? ""}
                        onChange={(event) => update(index, { number: toNumber(event.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        className="input input-small"
                        aria-label={`${label} name`}
                        value={row.name}
                        onChange={(event) => update(index, { name: event.target.value })}
                      />
                    </td>
                    <td>
                      <select
                        className="select input-small"
                        aria-label={`${label} type`}
                        value={row.type}
                        onChange={(event) => update(index, { type: event.target.value as LessonType })}
                      >
                        {LESSON_TYPES.map((type) => (
                          <option key={type.value} value={type.value}>
                            {type.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        className="input input-small num-input"
                        type="number"
                        min={1}
                        aria-label={`${label} first page`}
                        value={row.start_page ?? ""}
                        onChange={(event) => update(index, { start_page: toNumber(event.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        className="input input-small num-input"
                        type="number"
                        min={1}
                        aria-label={`${label} last page`}
                        value={row.end_page ?? ""}
                        onChange={(event) => update(index, { end_page: toNumber(event.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        className="input input-small num-input"
                        type="number"
                        min={1}
                        max={300}
                        aria-label={`${label} minutes`}
                        value={row.minutes ?? ""}
                        onChange={(event) => update(index, { minutes: toNumber(event.target.value) })}
                      />
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-quiet btn-small"
                        aria-label={`Remove ${label.toLowerCase()}`}
                        onClick={() => setRows((current) => current.filter((_, i) => i !== index))}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      <div className="row-between">
        <button
          type="button"
          className="btn btn-small"
          onClick={() =>
            setRows((current) => [...current, { number: nextNumber(), name: "", type: "lesson", start_page: null, end_page: null }])
          }
        >
          Add a lesson
        </button>
        <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : saveLabel}
        </button>
      </div>
      {problem ? <p className="field-error">{problem}</p> : null}
      <ErrorLine error={error} />
    </div>
  );
}
