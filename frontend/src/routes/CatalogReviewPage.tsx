import { useEffect, useState } from "react";
import { Navigate } from "react-router";

import { useImageSource } from "../api/images";
import {
  useCatalogEntries,
  useContribution,
  useEntryAction,
  useEntryAdmin,
  useQueue,
  useReview,
  type ContributionDetail,
} from "../api/parent";
import { useMe } from "../api/queries";
import { ErrorLine, TextArea, TextField, Toggle } from "../components/ui/Fields";
import { shortDate } from "../lib/dates";

type Tab = "open" | "all" | "entries";

const GROUP_LABELS: Record<string, string> = {
  structure: "Structure",
  identity: "Identity",
  privacy: "Privacy",
  spam: "Spam",
  copying: "Copying",
  cover: "Cover",
  link: "Link",
  behavior: "Behavior",
  agreement: "Agreement",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Waiting",
  asked: "Asked the family",
  approved: "Approved",
  merged: "Merged",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

const FIELD_LABELS: [string, string][] = [
  ["kind", "Kind"],
  ["author", "Author"],
  ["publisher", "Publisher"],
  ["series", "Series"],
  ["edition", "Edition"],
  ["isbn", "ISBN"],
  ["subject_code", "Subject"],
  ["grade", "Grade"],
  ["reading_kind", "Kind of book"],
  ["total_pages", "Total pages"],
  ["answer_key_start_page", "Answer key from page"],
  ["lesson_count", "Lessons"],
  ["measure", "Measured in"],
  ["minutes_per_session", "Minutes a session"],
  ["days_per_week", "Days a week"],
  ["for_parent", "For the parent"],
  ["website_url", "Website"],
  ["cover_url", "Lookup cover"],
];

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

interface Chapter {
  name: string;
  start_page: number;
}

interface Lesson {
  number: number | null;
  name: string | null;
  type: string;
  start_page: number | null;
  end_page: number | null;
}

interface ItemRef {
  role: string;
  title: string;
  entry_id: number | null;
  contribution_id: number | null;
}

function Contents({ data }: { data: Record<string, unknown> }) {
  const chapters = (data.chapters as Chapter[] | undefined) ?? [];
  const lessons = (data.lessons as Lesson[] | undefined) ?? [];
  const items = (data.items as ItemRef[] | undefined) ?? [];
  return (
    <div className="stack-lg">
      <dl className="kv">
        {FIELD_LABELS.filter(([name]) => data[name] !== undefined && data[name] !== null && data[name] !== "").map(([name, label]) => (
          <div key={name}>
            <dt>{label}</dt>
            <dd>{show(data[name])}</dd>
          </div>
        ))}
      </dl>
      {items.length ? (
        <div className="stack">
          <p className="role-title">Its books</p>
          <ul className="flags">
            {items.map((item, index) => (
              <li className="flag" key={index}>
                <span className="flag-where">{item.role}</span>: {item.title}{" "}
                <span className="muted small">
                  {item.entry_id ? `(catalog entry #${item.entry_id})` : item.contribution_id ? `(contribution #${item.contribution_id})` : "(not contributed)"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {chapters.length ? (
        <div className="stack">
          <p className="role-title">{chapters.length} chapters</p>
          <ol className="small">
            {chapters.map((chapter, index) => (
              <li key={index}>
                {chapter.name}, p. {chapter.start_page}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      {lessons.length ? (
        <div className="stack">
          <p className="role-title">{lessons.length} lessons</p>
          <div className="editor-scroll">
            <table className="editor-table">
              <thead>
                <tr>
                  <th scope="col">No.</th>
                  <th scope="col">Name</th>
                  <th scope="col">Type</th>
                  <th scope="col">Pages</th>
                </tr>
              </thead>
              <tbody>
                {lessons.map((lesson, index) => (
                  <tr key={index}>
                    <td>{show(lesson.number)}</td>
                    <td>{show(lesson.name)}</td>
                    <td>{lesson.type}</td>
                    <td>{lesson.start_page ? `${lesson.start_page}–${lesson.end_page ?? "?"}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function CoverImage({ url }: { url: string }) {
  const source = useImageSource(url);
  return source ? (
    <div className="cover">
      <img src={source} alt="The uploaded cover" />
    </div>
  ) : (
    <p className="muted small">Loading the cover…</p>
  );
}

function Actions({ detail }: { detail: ContributionDetail }) {
  const review = useReview(detail.id);
  const [action, setAction] = useState<"approve" | "merge" | "reject" | "ask">("approve");
  const isCurriculum = detail.kind === "curriculum";
  const originalTitle = String((isCurriculum ? detail.data.name : detail.data.title) ?? detail.title);
  const [title, setTitle] = useState(originalTitle);
  const [includeCover, setIncludeCover] = useState(true);
  const [replace, setReplace] = useState(false);
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const canMerge = !isCurriculum && detail.compare_entry && !detail.is_correction;

  if (detail.status !== "pending" && detail.status !== "asked") {
    return (
      <p className="notice">
        {STATUS_LABELS[detail.status] ?? detail.status}
        {detail.reviewed_by ? ` by ${detail.reviewed_by}` : ""}
        {detail.review_note ? `: ${detail.review_note}` : "."}
        {detail.result_entry_id ? ` Catalog entry #${detail.result_entry_id}.` : ""}
        {detail.result_curriculum_id ? ` Community curriculum #${detail.result_curriculum_id}.` : ""}
      </p>
    );
  }

  const submit = () => {
    if (action === "approve") {
      const edits = title.trim() && title.trim() !== originalTitle ? (isCurriculum ? { name: title.trim() } : { title: title.trim() }) : null;
      review.mutate({ action: "approve", body: { edits, include_cover: includeCover, note: note.trim() || null } });
    } else if (action === "merge" && detail.compare_entry) {
      review.mutate({
        action: "merge",
        body: { entry_id: detail.compare_entry.id, replace_details: replace, include_cover: includeCover, note: note.trim() || null },
      });
    } else if (action === "reject") {
      review.mutate({ action: "reject", body: { reason: text.trim() } });
    } else if (action === "ask") {
      review.mutate({ action: "ask", body: { question: text.trim() } });
    }
  };

  return (
    <section className="card stack" aria-label="Decide">
      <div className="chips">
        {(["approve", ...(canMerge ? ["merge"] : []), "reject", "ask"] as const).map((name) => (
          <button key={name} type="button" className="chip" aria-pressed={action === name} onClick={() => setAction(name as typeof action)}>
            {name === "approve" ? "Approve" : name === "merge" ? "Merge into the existing entry" : name === "reject" ? "Reject" : "Ask the family"}
          </button>
        ))}
      </div>
      {action === "approve" ? (
        <div className="form-grid">
          <TextField label={isCurriculum ? "Name" : "Title"} wide value={title} onChange={setTitle} hint="Tidy it if needed (capitals, a child's name)." />
          {detail.has_cover ? (
            <Toggle label="Include the uploaded cover" checked={includeCover} onChange={setIncludeCover} hint="Only a real published cover: no photos, no faces." />
          ) : null}
          <TextField label="Note (for the record)" wide value={note} onChange={setNote} />
        </div>
      ) : null}
      {action === "merge" && detail.compare_entry ? (
        <div className="stack">
          <p className="small">
            Counts this family toward <strong>{detail.compare_entry.title}</strong> (#{detail.compare_entry.id}) and links their copy to it.
          </p>
          <Toggle label="Use these details as the entry's new version" checked={replace} onChange={setReplace} hint="Only if this version is better than the catalog's." />
          {detail.has_cover ? <Toggle label="Include the uploaded cover" checked={includeCover} onChange={setIncludeCover} /> : null}
        </div>
      ) : null}
      {action === "reject" || action === "ask" ? (
        <TextArea
          label={action === "reject" ? "Why (the family sees this)" : "Your question (the family sees this)"}
          value={text}
          onChange={setText}
          rows={3}
          hint={action === "reject" ? "Their own copy keeps working; this only keeps it out of the catalog." : "Their next edit brings it back to this queue."}
        />
      ) : null}
      <div className="row">
        <button
          type="button"
          className={action === "reject" ? "btn btn-danger" : "btn btn-primary"}
          disabled={review.isPending || ((action === "reject" || action === "ask") && text.trim().length < 3)}
          onClick={submit}
        >
          {action === "approve" ? "Approve" : action === "merge" ? "Merge" : action === "reject" ? "Reject" : "Send the question"}
        </button>
      </div>
      {review.data?.left_out?.length ? <p className="notice">Left out (not in the catalog): {review.data.left_out.join(", ")}.</p> : null}
      <ErrorLine error={review.error} />
    </section>
  );
}

function ContributionView({ id }: { id: number }) {
  const query = useContribution(id);
  const detail = query.data;
  if (!detail) return query.isError ? <ErrorLine error={query.error} /> : <p className="muted">Loading…</p>;
  const reviewFlags = detail.flags.filter((flag) => flag.level === "review");
  const notes = detail.flags.filter((flag) => flag.level !== "review");
  return (
    <article className="stack-lg" aria-label={detail.title}>
      <div>
        <h2 className="section-title">{detail.title}</h2>
        <p className="card-meta">
          {detail.kind_label} · {STATUS_LABELS[detail.status] ?? detail.status} · {detail.contributor.label} ({detail.contributor.accepted} accepted,{" "}
          {detail.contributor.rejected} rejected) · sent {shortDate(detail.created_at.slice(0, 10))}
          {detail.is_correction ? " · a correction" : ""}
        </p>
      </div>

      {reviewFlags.length || notes.length ? (
        <section className="stack" aria-label="Flags">
          <ul className="flags">
            {[...reviewFlags, ...notes].map((flag, index) => (
              <li key={index} className={flag.level === "review" ? "flag flag-review" : "flag"}>
                <span className="flag-where">
                  {GROUP_LABELS[flag.group] ?? flag.group} · {flag.where}:
                </span>{" "}
                {flag.message}
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <p className="notice notice-success">No flags.</p>
      )}

      {detail.compare_entry && detail.changes ? (
        <section className="card stack" aria-label="Compared with the catalog">
          <p className="card-title">
            {detail.is_correction ? "Changes to" : "Looks like"} catalog entry #{detail.compare_entry.id}: {detail.compare_entry.title}
          </p>
          <p className="small">{detail.changes.summary}</p>
          {detail.changes.fields.length ? (
            <table className="preview-table">
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Catalog</th>
                  <th scope="col">This contribution</th>
                </tr>
              </thead>
              <tbody>
                {detail.changes.fields.map((change) => (
                  <tr key={change.field}>
                    <td>{change.field}</td>
                    <td>{show(change.catalog)}</td>
                    <td className="changed">{show(change.contributed)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {detail.changes.lessons_changed.length ? (
            <p className="small">
              Lessons {detail.changes.lessons_before} → {detail.changes.lessons_after}; changed: {detail.changes.lessons_changed.join(", ")}
            </p>
          ) : null}
        </section>
      ) : null}

      {detail.lookup ? (
        <p className="notice">
          The book lookup says: <strong>{detail.lookup.title}</strong>
          {detail.lookup.authors.length ? ` by ${detail.lookup.authors.join(", ")}` : ""}
          {detail.lookup.page_count ? `, ${detail.lookup.page_count} pages` : ""}.
        </p>
      ) : null}

      {detail.cover_url ? <CoverImage url={detail.cover_url} /> : null}
      <Contents data={detail.data} />
      <Actions key={`${detail.id}-${detail.status}`} detail={detail} />
    </article>
  );
}

function QueueTab({ status }: { status: "open" | "all" }) {
  const queue = useQueue(status);
  const [selected, setSelected] = useState<number | null>(null);
  const rows = queue.data ?? [];
  const current = selected ?? rows[0]?.id ?? null;
  return (
    <div className="review-layout">
      <section aria-label="Contributions">
        {queue.isPending ? <p className="muted">Loading…</p> : null}
        <ErrorLine error={queue.error} />
        {queue.isSuccess && rows.length === 0 ? (
          <p className="notice notice-success">{status === "open" ? "Nothing waiting. The queue is clear." : "Nothing yet."}</p>
        ) : null}
        <ul className="queue">
          {rows.map((row) => (
            <li key={row.id}>
              <button type="button" className="queue-item" aria-current={row.id === current} onClick={() => setSelected(row.id)}>
                <span className="result-title">{row.title}</span>
                <span className="row">
                  <span className="badge">{row.kind_label}</span>
                  {row.review_flags ? <span className="badge badge-missing">{row.review_flags} to check</span> : <span className="badge badge-ready">Clean</span>}
                  {row.is_correction ? <span className="badge badge-info">Correction</span> : null}
                  {row.has_cover ? <span className="badge badge-violet">Cover</span> : null}
                  {status === "all" ? <span className="badge">{STATUS_LABELS[row.status] ?? row.status}</span> : null}
                </span>
                <span className="muted small">
                  {row.contributor_label} · {shortDate(row.updated_at.slice(0, 10))}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {current !== null ? <ContributionView key={current} id={current} /> : null}
    </div>
  );
}

function EntryView({ id }: { id: number }) {
  const query = useEntryAdmin(id);
  const action = useEntryAction(id);
  const entry = query.data;
  if (!entry) return query.isError ? <ErrorLine error={query.error} /> : <p className="muted">Loading…</p>;
  return (
    <article className="stack-lg" aria-label={entry.title}>
      <div>
        <h2 className="section-title">{entry.title}</h2>
        <p className="card-meta">
          {entry.kind_label} · {entry.detail} · version {entry.version} · {entry.status === "published" ? "in search" : "retired (hidden from search)"}
        </p>
      </div>
      <div className="row">
        {entry.status === "published" ? (
          <button type="button" className="btn btn-danger btn-small" disabled={action.isPending} onClick={() => action.mutate({ action: "retire" })}>
            Retire (hide from search)
          </button>
        ) : (
          <button type="button" className="btn btn-small" disabled={action.isPending} onClick={() => action.mutate({ action: "publish" })}>
            Show in search again
          </button>
        )}
      </div>
      <section className="card stack" aria-label="Versions">
        <p className="card-title">Versions</p>
        <table className="preview-table">
          <thead>
            <tr>
              <th scope="col">Version</th>
              <th scope="col">Approved by</th>
              <th scope="col">When</th>
              <th scope="col">Note</th>
              <th scope="col">
                <span className="sr-only">Roll back</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {entry.versions.map((version) => (
              <tr key={version.version}>
                <td>{version.version}</td>
                <td>{version.approved_by}</td>
                <td>{shortDate(version.created_at.slice(0, 10))}</td>
                <td>{version.note ?? "—"}</td>
                <td>
                  {version.version === entry.version ? (
                    <span className="badge badge-ready">Current</span>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-small"
                      disabled={action.isPending}
                      onClick={() => action.mutate({ action: "rollback", version: version.version })}
                    >
                      Go back to this
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="field-hint">Going back adds a new version, so nothing is lost. Families keep their own copies.</p>
      </section>
      <Contents data={entry as unknown as Record<string, unknown>} />
      <ErrorLine error={action.error} />
    </article>
  );
}

function EntriesTab() {
  const [q, setQ] = useState("");
  const entries = useCatalogEntries(q.trim());
  const [selected, setSelected] = useState<number | null>(null);
  const rows = entries.data ?? [];
  return (
    <div className="review-layout">
      <section className="stack" aria-label="Catalog entries">
        <TextField label="Find an entry" type="search" value={q} onChange={setQ} placeholder="Title or ISBN" />
        <ul className="queue">
          {rows.map((row) => (
            <li key={row.id}>
              <button type="button" className="queue-item" aria-current={row.id === selected} onClick={() => setSelected(row.id)}>
                <span className="result-title">{row.title}</span>
                <span className="muted small">
                  {row.kind_label} · {row.detail}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {entries.isSuccess && rows.length === 0 ? <p className="muted">No entries yet.</p> : null}
      </section>
      {selected !== null ? <EntryView key={selected} id={selected} /> : null}
    </div>
  );
}

/** Settings → Admin: the community catalog's review queue and its entries. */
export function CatalogReviewPage() {
  const me = useMe();
  const [tab, setTab] = useState<Tab>("open");

  useEffect(() => {
    document.title = "Catalog review · Curiculy";
  }, []);

  if (!me.data) return me.isError ? <ErrorLine error={me.error} /> : <p className="muted">Loading…</p>;
  if (!me.data.is_admin) return <Navigate to="/library" replace />;

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Catalog review</h1>
          <p className="page-lede">
            Everything families add goes to the community catalog through here. Check the flags, then approve, merge,
            reject with a reason, or ask the family. Families' own copies work either way.
          </p>
        </div>
      </div>
      <div className="chips" role="tablist" aria-label="Show">
        {(
          [
            ["open", "Waiting for review"],
            ["all", "Everything"],
            ["entries", "Catalog entries"],
          ] as [Tab, string][]
        ).map(([name, label]) => (
          <button key={name} type="button" role="tab" className="chip" aria-selected={tab === name} aria-pressed={tab === name} onClick={() => setTab(name)}>
            {label}
          </button>
        ))}
      </div>
      {tab === "entries" ? <EntriesTab /> : <QueueTab key={tab} status={tab} />}
    </>
  );
}
