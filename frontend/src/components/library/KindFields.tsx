import type { LibraryCreate, LibraryFields, LibraryItem, Reference } from "../../api/parent";
import { NumberField, SelectField, TextField, Toggle } from "../ui/Fields";

/** Everything a library item can have, as the forms hold it ("" for empty). */
export interface Draft {
  kind: string;
  title: string;
  author: string;
  publisher: string;
  edition: string;
  isbn: string;
  subject_code: string;
  grade: string;
  reading_kind: string;
  total_pages: number | null;
  answer_key_start_page: number | null;
  lesson_count: number | null;
  measure: string;
  minutes_per_session: number | null;
  days_per_week: number | null;
  for_parent: boolean;
  website_url: string;
  login_note: string;
  cover_url: string;
}

export function emptyDraft(): Draft {
  return {
    kind: "",
    title: "",
    author: "",
    publisher: "",
    edition: "",
    isbn: "",
    subject_code: "",
    grade: "",
    reading_kind: "",
    total_pages: null,
    answer_key_start_page: null,
    lesson_count: null,
    measure: "",
    minutes_per_session: null,
    days_per_week: null,
    for_parent: false,
    website_url: "",
    login_note: "",
    cover_url: "",
  };
}

export function draftFromItem(item: LibraryItem): Draft {
  return {
    kind: item.kind,
    title: item.title,
    author: item.author ?? "",
    publisher: item.publisher ?? "",
    edition: item.edition ?? "",
    isbn: item.isbn ?? "",
    subject_code: item.subject_code ?? "",
    grade: item.grade ?? "",
    reading_kind: item.reading_kind ?? "",
    total_pages: item.total_pages ?? null,
    answer_key_start_page: item.answer_key_start_page ?? null,
    lesson_count: item.lesson_count ?? null,
    measure: item.measure ?? "",
    minutes_per_session: item.minutes_per_session ?? null,
    days_per_week: item.days_per_week ?? null,
    for_parent: item.for_parent,
    website_url: item.website_url ?? "",
    login_note: item.login_note ?? "",
    cover_url: "",
  };
}

const text = (value: string) => (value.trim() ? value.trim() : null);

/** The fields to save. The cover is handled on its own (upload or lookup). */
export function draftToFields(draft: Draft): LibraryFields {
  return {
    title: text(draft.title),
    author: text(draft.author),
    publisher: text(draft.publisher),
    edition: text(draft.edition),
    isbn: text(draft.isbn),
    subject_code: text(draft.subject_code),
    grade: text(draft.grade),
    reading_kind: text(draft.reading_kind),
    total_pages: draft.total_pages,
    answer_key_start_page: draft.answer_key_start_page,
    lesson_count: draft.lesson_count,
    measure: text(draft.measure),
    minutes_per_session: draft.minutes_per_session,
    days_per_week: draft.days_per_week,
    for_parent: draft.for_parent,
    website_url: text(draft.website_url),
    login_note: text(draft.login_note),
  };
}

export function draftToCreate(draft: Draft): LibraryCreate {
  return {
    ...draftToFields(draft),
    kind: draft.kind,
    title: draft.title.trim(),
    cover_url: text(draft.cover_url),
  };
}

const READING_KINDS = [
  { value: "novel", label: "Novel" },
  { value: "biography", label: "Biography" },
  { value: "poetry", label: "Poetry" },
  { value: "picture_book", label: "Picture book" },
  { value: "read_aloud", label: "Read-aloud" },
  { value: "other", label: "Something else" },
];

const DAYS = [1, 2, 3, 4, 5, 6, 7].map((day) => ({ value: String(day), label: `${day} day${day === 1 ? "" : "s"} a week` }));

export function subjectOptions(reference: Reference | undefined) {
  return (reference?.subjects ?? []).map((subject) => ({ value: subject.code, label: subject.name }));
}

export function gradeOptions(reference: Reference | undefined) {
  return (reference?.grades ?? []).map((grade) => ({ value: grade.code, label: grade.label }));
}

/**
 * The questions for one kind of book, each saying why it's asked. Fields
 * marked * are needed before it can be scheduled; everything else is optional.
 */
export function KindFields({
  draft,
  onChange,
  reference,
}: {
  draft: Draft;
  onChange: (patch: Partial<Draft>) => void;
  reference: Reference | undefined;
}) {
  const subjects = subjectOptions(reference);
  const grades = gradeOptions(reference);

  const subject = (label = "Subject", required = true, hint?: string) => (
    <SelectField
      label={label}
      required={required}
      value={draft.subject_code}
      onChange={(value) => onChange({ subject_code: value })}
      options={subjects}
      hint={hint ?? "Connects this to your child's subjects and your state's requirements."}
    />
  );
  const grade = (
    <SelectField
      label="Grade"
      required
      value={draft.grade}
      onChange={(value) => onChange({ grade: value })}
      options={grades}
      hint="Helps match it to the right child, and to the right edition in the catalog."
    />
  );
  const pages = (hint: string) => (
    <NumberField
      label="Total pages"
      required
      max={5000}
      value={draft.total_pages}
      onChange={(value) => onChange({ total_pages: value })}
      hint={hint}
    />
  );

  if (draft.kind === "reading_book") {
    return (
      <div className="form-grid">
        <TextField
          label="Author"
          required
          value={draft.author}
          onChange={(value) => onChange({ author: value })}
          hint="Your reading list and state records name each book's author."
        />
        {pages("Curiculy divides the pages into daily reading, and re-plans them when a day is missed.")}
        <SelectField
          label="Kind of book"
          value={draft.reading_kind}
          onChange={(value) => onChange({ reading_kind: value })}
          options={READING_KINDS}
          placeholder="Not sure"
        />
        {subject("Counts toward", false, "Reading, unless you pick something else (a biography can count toward History).")}
      </div>
    );
  }

  if (draft.kind === "textbook") {
    return (
      <div className="form-grid">
        <TextField
          label="Publisher"
          required
          value={draft.publisher}
          onChange={(value) => onChange({ publisher: value })}
          hint="The publisher and edition make sure the lesson list matches the book you own."
        />
        <TextField
          label="Edition or year"
          required
          value={draft.edition}
          onChange={(value) => onChange({ edition: value })}
          placeholder="4th edition, or 2019"
        />
        {subject()}
        {grade}
        {pages("Curiculy checks that every lesson's pages fit inside the book.")}
        <SelectField
          label="Designed for"
          value={draft.days_per_week ? String(draft.days_per_week) : ""}
          onChange={(value) => onChange({ days_per_week: value ? Number(value) : null })}
          options={DAYS}
          placeholder="Not sure"
          hint="Many programs are written for 4 or 5 days a week. The calendar paces the lessons to match."
        />
        <Toggle
          label="This is a teacher's edition or answer key"
          checked={draft.for_parent}
          onChange={(value) => onChange({ for_parent: value })}
          hint="It's for you, so it needs no lesson list and never goes on your child's calendar."
        />
      </div>
    );
  }

  if (draft.kind === "workbook") {
    return (
      <div className="form-grid">
        {subject("Subject", true, "Pick the main one. A workbook that mixes subjects can give each chapter its own.")}
        {grade}
        {pages("Curiculy spreads the pages across your school days.")}
        <NumberField
          label="Answer key starts on page"
          max={5000}
          value={draft.answer_key_start_page}
          onChange={(value) => onChange({ answer_key_start_page: value })}
          hint="Leave empty if there's none. Answer pages are never scheduled."
        />
        <NumberField
          label="Numbered lessons (if it has them)"
          max={1000}
          value={draft.lesson_count}
          onChange={(value) => onChange({ lesson_count: value })}
        />
        <TextField label="Publisher or series" value={draft.publisher} onChange={(value) => onChange({ publisher: value })} />
      </div>
    );
  }

  if (draft.kind === "online_program") {
    return (
      <div className="form-grid">
        <TextField
          label="Website link"
          type="url"
          required
          wide
          value={draft.website_url}
          onChange={(value) => onChange({ website_url: value })}
          placeholder="https://www.ixl.com"
          hint="It opens from the lesson on the calendar and on your child's trail."
        />
        {subject()}
        {grade}
        <SelectField
          label="Measured in"
          required
          value={draft.measure}
          onChange={(value) => onChange({ measure: value })}
          options={[
            { value: "lessons", label: "Lessons (it has a set number)" },
            { value: "minutes", label: "Minutes (time on the site)" },
          ]}
          hint="Online work is scheduled by lessons or by minutes."
        />
        {draft.measure === "lessons" ? (
          <NumberField
            label="Number of lessons"
            required
            max={1000}
            value={draft.lesson_count}
            onChange={(value) => onChange({ lesson_count: value })}
          />
        ) : null}
        {draft.measure === "minutes" ? (
          <NumberField
            label="Minutes a session"
            required
            max={300}
            value={draft.minutes_per_session}
            onChange={(value) => onChange({ minutes_per_session: value })}
          />
        ) : null}
        <SelectField
          label="Days a week"
          required
          value={draft.days_per_week ? String(draft.days_per_week) : ""}
          onChange={(value) => onChange({ days_per_week: value ? Number(value) : null })}
          options={DAYS}
          hint="The calendar schedules sessions on this many school days each week."
        />
        <TextField
          label="A note for you"
          wide
          value={draft.login_note}
          onChange={(value) => onChange({ login_note: value })}
          placeholder="Log in as Ada"
          hint="Never a password: Curiculy doesn't keep sign-ins for other sites."
        />
      </div>
    );
  }

  return null;
}
