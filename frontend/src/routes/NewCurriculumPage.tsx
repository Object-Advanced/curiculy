import { useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { useCreateCurriculum, useCurriculumFromCommunity, useLibrary, useSuggestions } from "../api/parent";
import { BookCover } from "../components/library/BookCover";
import { PlannerIntro } from "../components/planner/PlannerIntro";
import { Suggestions } from "../components/planner/Suggestions";
import { ErrorLine } from "../components/ui/Fields";

/**
 * Starting a curriculum: pick its textbook, then start from what other
 * families built around it, or build your own.
 */
export function NewCurriculumPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const library = useLibrary();
  const textbookId = params.get("textbook") ? Number(params.get("textbook")) : null;
  const suggestions = useSuggestions(textbookId);
  const create = useCreateCurriculum();
  const adopt = useCurriculumFromCommunity();

  useEffect(() => {
    document.title = "Plan a curriculum · Curiculy";
  }, []);

  const textbooks = (library.data ?? []).filter((item) => item.kind === "textbook");
  const picked = textbooks.find((item) => item.id === textbookId) ?? null;

  const open = (id: number) => navigate(`/planner/${id}`, { replace: true });

  return (
    <>
      <div className="page-head">
        <div>
          <Link className="back-link" to="/planner">
            ← Curriculum planner
          </Link>
          <h1 className="page-title">Plan a curriculum</h1>
        </div>
      </div>

      {picked ? null : <PlannerIntro />}

      <section className="card stack-lg" aria-labelledby="pick-textbook">
        <div>
          <h2 className="section-title" id="pick-textbook">
            Which textbook is it built around?
          </h2>
          <p className="page-lede">
            The textbook is the main book you teach this subject from. Its lessons set the pace. Teacher's editions are
            added later, as something for you.
          </p>
        </div>
        {library.isPending ? <p className="muted">Loading your library…</p> : null}
        {library.isSuccess && textbooks.length === 0 ? (
          <div className="notice">
            <p>There's no textbook in your library yet. Add one first; it takes a few minutes, or seconds if it's in the catalog.</p>
            <p>
              <Link className="btn btn-primary btn-small" to="/library?add=1">
                Add a textbook to your library
              </Link>
            </p>
          </div>
        ) : null}
        {textbooks.length > 0 ? (
          <fieldset className="choice-cards">
            <legend className="sr-only">Textbook</legend>
            {textbooks.map((item) => (
              <label className="choice-card" key={item.id}>
                <input
                  type="radio"
                  name="textbook"
                  checked={item.id === textbookId}
                  onChange={() => setParams({ textbook: String(item.id) }, { replace: true })}
                />
                <span className="row">
                  <BookCover small url={item.cover.url} title={item.title} kindLabel={item.kind_label} subjectCode={item.subject_code} kind={item.kind} />
                  <span className="choice-text">
                    <span className="choice-title">{item.title}</span>
                    <span className="choice-hint">
                      {[item.subject_name, item.grade ? `Grade ${item.grade}` : null].filter(Boolean).join(" · ")}
                    </span>
                    <span className={item.ready ? "badge badge-ready" : "badge badge-missing"}>
                      {item.ready ? "Ready" : "Still needs its lesson list or details"}
                    </span>
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
        ) : null}
        {textbooks.length > 0 ? (
          <p className="field-hint">
            Not here? <Link to="/library?add=1">Add a textbook to your library</Link>.
          </p>
        ) : null}
      </section>

      {picked ? (
        <>
          {suggestions.data ? (
            <Suggestions
              data={suggestions.data}
              busy={adopt.isPending}
              onUse={(communityCurriculumId, entryIds) =>
                adopt.mutate(
                  { community_curriculum_id: communityCurriculumId, entry_ids: entryIds },
                  { onSuccess: (curriculum) => open(curriculum.id) },
                )
              }
            />
          ) : null}
          <ErrorLine error={adopt.error} />
          <section className="card row-between" aria-labelledby="build-own">
            <div>
              <h2 className="card-title" id="build-own">
                {suggestions.data?.curricula.length ? "Or build your own" : "Build it"}
              </h2>
              <p className="card-meta">
                {suggestions.data?.curricula.length
                  ? `Start with just ${picked.title}, and add what goes with it yourself.`
                  : suggestions.data?.message ?? `Start with ${picked.title}, then add what goes with it.`}
              </p>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              disabled={create.isPending}
              onClick={() => create.mutate({ textbook_id: picked.id }, { onSuccess: (curriculum) => open(curriculum.id) })}
            >
              {create.isPending ? "Starting…" : `Start with ${picked.title}`}
            </button>
          </section>
          <ErrorLine error={create.error} />
        </>
      ) : null}
    </>
  );
}
