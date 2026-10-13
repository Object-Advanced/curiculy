/** "How curricula work", shown the first time a family plans one (and on request). */
export function PlannerIntro({ onHide }: { onHide?: () => void }) {
  return (
    <section className="card stack-lg" aria-labelledby="planner-intro-title">
      <div className="row-between">
        <h2 className="section-title" id="planner-intro-title">
          How curricula work
        </h2>
        {onHide ? (
          <button type="button" className="btn btn-quiet btn-small" onClick={onHide}>
            Got it, hide this
          </button>
        ) : null}
      </div>
      <p className="step-lede">
        A curriculum is your plan for one subject. It's usually built around <strong>one textbook</strong>, the main
        book you teach from, and everything that goes with it. No textbook? Build it around a workbook, a website or a
        book, and choose how fast it goes. (To schedule one book by itself, use <strong>Schedule it</strong> in the
        Library.)
      </p>
      <ol className="explain">
        <li>
          <span className="explain-num">1</span>
          <strong>Pick the textbook.</strong>
          <span className="muted small">
            Its lessons set the pace: one lesson each school day, quizzes and tests in their place.
          </span>
        </li>
        <li>
          <span className="explain-num">2</span>
          <strong>Add what goes with it.</strong>
          <span className="muted small">
            Workbooks (their pages are spread over the same days), online sites (on their own days a week), books to
            read alongside, and the teacher's edition (for you, never on your child's calendar).
          </span>
        </li>
        <li>
          <span className="explain-num">3</span>
          <strong>Put it on the calendar.</strong>
          <span className="muted small">
            Pick your children and a start date. You see every date before anything is saved, and days off are skipped.
          </span>
        </li>
      </ol>
      <p className="field-hint">
        The child is picked when you schedule, so one curriculum can serve two children, or be used again next year.
      </p>
    </section>
  );
}
