import { useState } from "react";
import { Link } from "react-router";

import {
  useAddReading,
  useLibrary,
  useReference,
  useRemoveReading,
  useUpdateReading,
  type ReadingEntry,
} from "../../api/parent";
import { subjectOptions } from "../library/KindFields";
import { ErrorLine, SelectField, TextField } from "../ui/Fields";
import { Modal } from "../ui/Modal";

type Status = ReadingEntry["status"];

const STATUSES: { value: Status; label: string }[] = [
  { value: "up_next", label: "Up next" },
  { value: "reading", label: "Reading now" },
  { value: "finished", label: "Finished" },
];

interface Fields {
  status: Status;
  started_on: string;
  finished_on: string;
  counts_toward: string;
}

/** Where it is, when it started and finished, and what it counts toward. */
function ReadingFields({ fields, onChange }: { fields: Fields; onChange: (patch: Partial<Fields>) => void }) {
  const reference = useReference();
  return (
    <>
      <fieldset className="field">
        <legend className="field-label">Where are they with it?</legend>
        <div className="chips">
          {STATUSES.map((option) => (
            <button
              key={option.value}
              type="button"
              className="chip"
              aria-pressed={fields.status === option.value}
              onClick={() => onChange({ status: option.value })}
            >
              {option.label}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="form-grid">
        {fields.status !== "up_next" ? (
          <TextField
            label="Started"
            type="date"
            value={fields.started_on}
            onChange={(value) => onChange({ started_on: value })}
            hint="Leave it empty for today."
          />
        ) : null}
        {fields.status === "finished" ? (
          <TextField
            label="Finished"
            type="date"
            value={fields.finished_on}
            onChange={(value) => onChange({ finished_on: value })}
            hint="Leave it empty for today."
          />
        ) : null}
        <SelectField
          label="Counts toward"
          value={fields.counts_toward}
          onChange={(value) => onChange({ counts_toward: value })}
          options={subjectOptions(reference.data)}
          placeholder="Its own subject (Reading, if none)"
          hint="A biography can count toward History, a nature book toward Science."
        />
      </div>
    </>
  );
}

const dates = (fields: Fields) => ({
  started_on: fields.status === "up_next" ? null : fields.started_on || null,
  finished_on: fields.status === "finished" ? fields.finished_on || null : null,
});

/** Put a book from the Library on one child's list. */
export function AddReadingModal({
  studentId,
  studentName,
  onList,
  onClose,
}: {
  studentId: number;
  studentName: string;
  onList: number[];
  onClose: () => void;
}) {
  const library = useLibrary();
  const add = useAddReading();
  const [bookId, setBookId] = useState("");
  const [fields, setFields] = useState<Fields>({ status: "up_next", started_on: "", finished_on: "", counts_toward: "" });
  const taken = new Set(onList);
  const books = (library.data ?? []).filter((item) => item.kind === "reading_book" && !taken.has(item.id));
  const change = (patch: Partial<Fields>) => setFields((current) => ({ ...current, ...patch }));

  return (
    <Modal
      title={`Add a book to ${studentName}'s list`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-quiet" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!bookId || add.isPending}
            onClick={() =>
              add.mutate(
                {
                  student_id: studentId,
                  library_item_id: Number(bookId),
                  status: fields.status,
                  counts_toward: fields.counts_toward || null,
                  ...dates(fields),
                },
                { onSuccess: onClose },
              )
            }
          >
            {add.isPending ? "Adding…" : "Add it"}
          </button>
        </>
      }
    >
      <div className="stack-lg">
        {library.isSuccess && books.length === 0 ? (
          <p className="notice">
            Every book in your Library is already on {studentName}'s list.{" "}
            <Link to="/library?add=1">Add a book to your Library</Link> first.
          </p>
        ) : (
          <SelectField
            label="Book"
            required
            value={bookId}
            onChange={setBookId}
            options={books.map((book) => ({ value: String(book.id), label: book.author ? `${book.title} (${book.author})` : book.title }))}
            placeholder={library.isPending ? "Loading your books…" : "Choose a book…"}
            hint={
              <>
                Books from your Library. Not there yet? <Link to="/library?add=1">Add it to your Library</Link>, then come
                back.
              </>
            }
          />
        )}
        <ReadingFields fields={fields} onChange={change} />
        <ErrorLine error={add.error} />
      </div>
    </Modal>
  );
}

/** Change where a child is with a book, or take it off their list. */
export function EditReadingModal({ entry, onClose }: { entry: ReadingEntry; onClose: () => void }) {
  const update = useUpdateReading();
  const remove = useRemoveReading();
  const [confirming, setConfirming] = useState(false);
  const [fields, setFields] = useState<Fields>({
    status: entry.status,
    started_on: entry.started_on ?? "",
    finished_on: entry.finished_on ?? "",
    counts_toward: entry.counts_toward,
  });
  const change = (patch: Partial<Fields>) => setFields((current) => ({ ...current, ...patch }));

  return (
    <Modal
      title={entry.book.title}
      onClose={onClose}
      footer={
        <>
          {confirming ? (
            <div className="row">
              <span className="small">
                Take it off {entry.student_name}'s list?{entry.scheduled ? " Its reading stays on the calendar." : ""}
              </span>
              <button
                type="button"
                className="btn btn-danger btn-small"
                disabled={remove.isPending}
                onClick={() => remove.mutate(entry.id, { onSuccess: onClose })}
              >
                Yes, take it off
              </button>
              <button type="button" className="btn btn-quiet btn-small" onClick={() => setConfirming(false)}>
                Keep it
              </button>
            </div>
          ) : (
            <button type="button" className="btn btn-danger btn-small" onClick={() => setConfirming(true)}>
              Take it off the list
            </button>
          )}
          <button
            type="button"
            className="btn btn-primary"
            disabled={update.isPending}
            onClick={() =>
              update.mutate(
                { id: entry.id, body: { status: fields.status, counts_toward: fields.counts_toward || null, ...dates(fields) } },
                { onSuccess: onClose },
              )
            }
          >
            {update.isPending ? "Saving…" : "Save"}
          </button>
        </>
      }
    >
      <div className="stack-lg">
        {entry.scheduled ? (
          <p className="field-hint">
            Its reading is on {entry.student_name}'s calendar ({entry.lessons_done} of {entry.lessons_total} done). It
            moves along by itself as those are checked off.
          </p>
        ) : null}
        <ReadingFields fields={fields} onChange={change} />
        <ErrorLine error={update.error ?? remove.error} />
      </div>
    </Modal>
  );
}

/** The next step for a book, in one tap: start it, or finish it (today, on the family's clock). */
export function useReadingStep() {
  const update = useUpdateReading();
  const step = (entry: ReadingEntry) => {
    update.mutate({ id: entry.id, body: { status: entry.status === "up_next" ? "reading" : "finished" } });
  };
  return { step, pending: update.isPending, error: update.error };
}
