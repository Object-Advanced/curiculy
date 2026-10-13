import { useEffect, useState } from "react";
import { Link } from "react-router";

import { useCurricula, type Curriculum } from "../api/parent";
import { BookCover } from "../components/library/BookCover";
import { PlannerIntro } from "../components/planner/PlannerIntro";
import { ErrorLine } from "../components/ui/Fields";
import { shortDate } from "../lib/dates";

const INTRO_KEY = "curiculy.planner-intro-hidden";

function readHidden(): boolean {
  try {
    return window.localStorage.getItem(INTRO_KEY) === "1";
  } catch {
    return false;
  }
}

function roleCounts(curriculum: Curriculum): string {
  const counts = new Map<string, number>();
  for (const item of curriculum.items) counts.set(item.role_label, (counts.get(item.role_label) ?? 0) + 1);
  return [...counts].map(([label, count]) => `${count} ${label.toLowerCase()}${count === 1 ? "" : "s"}`).join(" · ");
}

function CurriculumCard({ curriculum }: { curriculum: Curriculum }) {
  const textbook = curriculum.items.find((item) => item.role === "textbook")?.item;
  const waiting = curriculum.readiness.missing.length + curriculum.readiness.problems.length;
  return (
    <li className="card curriculum-card">
      {textbook ? (
        <BookCover
          small
          url={textbook.cover.url}
          title={textbook.title}
          kindLabel={textbook.kind_label}
          subjectCode={textbook.subject_code}
          kind={textbook.kind}
        />
      ) : (
        <BookCover small url={null} title={curriculum.name} kindLabel="Curriculum" subjectCode={curriculum.subject_code} kind="textbook" />
      )}
      <div className="stack">
        <div>
          <h2 className="card-title">
            <Link to={`/planner/${curriculum.id}`}>{curriculum.name}</Link>
          </h2>
          <p className="card-meta">
            {[curriculum.subject_name, curriculum.grade ? `Grade ${curriculum.grade}` : null, roleCounts(curriculum)]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="row">
          {curriculum.readiness.ready ? (
            <span className="badge badge-ready">Ready to schedule</span>
          ) : (
            <span className="badge badge-missing">
              {waiting} thing{waiting === 1 ? "" : "s"} to finish
            </span>
          )}
          {curriculum.community_curriculum_id ? <span className="badge badge-violet">From other families</span> : null}
        </div>
        {curriculum.courses.map((course) => (
          <p className="small" key={course.id}>
            On {course.student_name}'s calendar: {shortDate(course.start_date)}
            {course.end_date ? ` to ${shortDate(course.end_date)}` : ""} ({course.lessons_scheduled} lessons)
          </p>
        ))}
      </div>
    </li>
  );
}

/** The Curriculum planner: every curriculum the family has built, and a way to start one. */
export function PlannerPage() {
  const curricula = useCurricula();
  const [hidden, setHidden] = useState(readHidden);

  useEffect(() => {
    document.title = "Curriculum planner · Curiculy";
  }, []);

  const list = curricula.data ?? [];
  const showIntro = !hidden || (curricula.isSuccess && list.length === 0);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Curriculum planner</h1>
          <p className="page-lede">
            Plan each subject: a textbook, plus the workbooks, websites and books that go with it. Then put it on your
            children's calendars.
          </p>
        </div>
        <div className="page-actions">
          {hidden && list.length > 0 ? (
            <button
              type="button"
              className="btn btn-quiet"
              onClick={() => {
                setHidden(false);
                try {
                  window.localStorage.removeItem(INTRO_KEY);
                } catch {
                  /* private mode */
                }
              }}
            >
              How this works
            </button>
          ) : null}
          <Link className="btn btn-primary" to="/planner/new">
            Plan a curriculum
          </Link>
        </div>
      </div>

      {showIntro ? (
        <PlannerIntro
          onHide={
            list.length > 0
              ? () => {
                  setHidden(true);
                  try {
                    window.localStorage.setItem(INTRO_KEY, "1");
                  } catch {
                    /* private mode: hidden for this visit */
                  }
                }
              : undefined
          }
        />
      ) : null}

      {curricula.isError ? <ErrorLine error={curricula.error} /> : null}
      {curricula.isPending ? <p className="muted">Loading your curricula…</p> : null}
      {list.length > 0 ? (
        <ul className="curricula" aria-label="Your curricula">
          {list.map((curriculum) => (
            <CurriculumCard key={curriculum.id} curriculum={curriculum} />
          ))}
        </ul>
      ) : null}
    </>
  );
}
