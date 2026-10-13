import type { Readiness } from "../../api/parent";

interface Missing {
  field: string;
  label: string;
  reason: string;
}

interface Problem {
  level: string;
  where: string;
  message: string;
}

/**
 * What's still needed before something can be scheduled, each with why, in
 * plain words. "Fix" problems block scheduling; "worth a look" ones don't.
 */
export function Checklist({
  ready,
  missing,
  problems,
  readyText = "Ready to schedule.",
}: {
  ready: boolean;
  missing: Missing[];
  problems: Problem[];
  readyText?: string;
}) {
  if (ready && problems.length === 0) {
    return (
      <ul className="checklist">
        <li className="check-ok">
          <span className="check-mark" aria-hidden="true">
            ✓
          </span>
          <span>{readyText}</span>
        </li>
      </ul>
    );
  }
  return (
    <ul className="checklist">
      {ready ? (
        <li className="check-ok">
          <span className="check-mark" aria-hidden="true">
            ✓
          </span>
          <span>{readyText}</span>
        </li>
      ) : null}
      {missing.map((item) => (
        <li key={`m-${item.field}`} className="check-missing">
          <span className="check-mark" aria-hidden="true">
            !
          </span>
          <span>
            <strong>Still needed: {item.label}.</strong>
            <span className="check-why">{item.reason}</span>
          </span>
        </li>
      ))}
      {problems.map((problem, index) => (
        <li key={`p-${index}`} className={problem.level === "fix" ? "check-fix" : "check-look"}>
          <span className="check-mark" aria-hidden="true">
            {problem.level === "fix" ? "×" : "?"}
          </span>
          <span>
            <strong>
              {problem.level === "fix" ? "Fix" : "Worth a look"}: {problem.where}.
            </strong>
            <span className="check-why">{problem.message}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function ReadinessList({ readiness }: { readiness: Readiness }) {
  return <Checklist ready={readiness.ready} missing={readiness.missing} problems={readiness.problems} />;
}
