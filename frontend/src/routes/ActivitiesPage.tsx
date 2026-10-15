import { useEffect, useState } from "react";

import { useActivities, type Activity } from "../api/parent";
import { useStudents } from "../api/queries";
import { ActivityForm } from "../components/activities/ActivityForm";
import { ActivityPhoto } from "../components/activities/ActivityPhoto";
import { ErrorLine } from "../components/ui/Fields";
import { dayOf, monthName, weekdayShort } from "../lib/dates";

/** "October 2026" groups, newest first (the list already is). */
function byMonth(activities: Activity[]): { label: string; items: Activity[] }[] {
  const groups: { label: string; items: Activity[] }[] = [];
  for (const activity of activities) {
    const label = `${monthName(activity.on_date)} ${activity.on_date.slice(0, 4)}`;
    const last = groups[groups.length - 1];
    if (last?.label === label) last.items.push(activity);
    else groups.push({ label, items: [activity] });
  }
  return groups;
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function ActivityCard({ activity, onEdit }: { activity: Activity; onEdit: () => void }) {
  const meta = [
    activity.students.map((child) => child.name).join(", "),
    activity.minutes ? `${activity.minutes} min` : null,
  ].filter(Boolean);
  return (
    <li className="card activity-card">
      <p className="activity-date" aria-hidden="true">
        <span>{weekdayShort(activity.on_date)}</span>
        <strong>{dayOf(activity.on_date)}</strong>
      </p>
      <div className="stack">
        <div>
          <h3 className="card-title">{activity.title}</h3>
          <p className="card-meta">
            <span className="sr-only">
              {monthName(activity.on_date)} {dayOf(activity.on_date)}:{" "}
            </span>
            {meta.join(" · ")}
          </p>
        </div>
        {activity.subjects.length ? (
          <div className="row">
            {activity.subjects.map((subject) => (
              <span className="badge badge-info" key={subject.code}>
                {subject.name}
              </span>
            ))}
          </div>
        ) : (
          <p className="small muted">No subject yet: add one so it counts on the records.</p>
        )}
        {activity.notes ? <p className="small">{activity.notes}</p> : null}
        {activity.evidence.length ? (
          <ul className="photo-strip" aria-label="Photos">
            {activity.evidence.map((photo) => (
              <li key={photo.id}>
                <ActivityPhoto filePath={photo.file_path} label={activity.title} />
              </li>
            ))}
          </ul>
        ) : null}
        <div className="row">
          {activity.link_url ? (
            <a className="btn btn-small" href={activity.link_url} target="_blank" rel="noreferrer noopener">
              Open the link ({hostOf(activity.link_url)})
            </a>
          ) : null}
          <button type="button" className="btn btn-quiet btn-small" onClick={onEdit} aria-label={`Change ${activity.title}`}>
            Change
          </button>
        </div>
      </div>
    </li>
  );
}

/**
 * Activities: PE, music, art, field trips, co-op classes, anything without a
 * curriculum. Each counts toward one or more subjects, for one child or
 * several, and its photos are work samples.
 */
export function ActivitiesPage() {
  const students = useStudents(true);
  const activities = useActivities();
  const [childId, setChildId] = useState<number | null>(null);
  const [editing, setEditing] = useState<Activity | "new" | null>(null);

  useEffect(() => {
    document.title = "Activities · Curiculy";
  }, []);

  const kids = students.data ?? [];
  const all = activities.data ?? [];
  const shown = childId === null ? all : all.filter((activity) => activity.students.some((child) => child.student_id === childId));

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Activities</h1>
          <p className="page-lede">
            PE, music, art, field trips, co-op classes: anything without a curriculum. Each one counts toward a subject,
            and its photos are work samples in your records.
          </p>
        </div>
        <div className="page-actions">
          {kids.length ? (
            <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>
              Log an activity
            </button>
          ) : null}
        </div>
      </div>

      {students.isSuccess && kids.length === 0 ? (
        <p className="notice">Add your children first (Kids, in the menu above). Then you can log what they do.</p>
      ) : null}

      {kids.length > 1 && all.length > 0 ? (
        <div className="chips" aria-label="Show">
          <button type="button" className="chip" aria-pressed={childId === null} onClick={() => setChildId(null)}>
            Everyone <span className="chip-count">{all.length}</span>
          </button>
          {kids.map((kid) => (
            <button key={kid.id} type="button" className="chip" aria-pressed={childId === kid.id} onClick={() => setChildId(kid.id)}>
              {kid.name}{" "}
              <span className="chip-count">
                {all.filter((activity) => activity.students.some((child) => child.student_id === kid.id)).length}
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {activities.isError ? <ErrorLine error={activities.error} /> : null}
      {activities.isPending ? <p className="muted">Loading activities…</p> : null}
      {activities.isSuccess && all.length === 0 && kids.length > 0 ? (
        <section className="card empty-shelf" aria-label="No activities yet">
          <h2 className="section-title">Nothing logged yet</h2>
          <p className="step-lede">
            Log the things school doesn't have a book for: a 5K race for PE, a piano lesson for Music, a visit to the fire
            station for Safety. Add a photo and it's a work sample too.
          </p>
          <button type="button" className="btn btn-primary" onClick={() => setEditing("new")}>
            Log an activity
          </button>
        </section>
      ) : null}

      {byMonth(shown).map((group) => (
        <section className="stack" key={group.label} aria-label={group.label}>
          <h2 className="section-title">{group.label}</h2>
          <ul className="activity-list">
            {group.items.map((activity) => (
              <ActivityCard key={activity.id} activity={activity} onEdit={() => setEditing(activity)} />
            ))}
          </ul>
        </section>
      ))}

      {editing ? (
        <ActivityForm
          activity={editing === "new" ? null : editing}
          students={kids}
          defaultStudentIds={childId !== null ? [childId] : kids.length === 1 ? [kids[0]!.id] : []}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}
