import { useState } from "react";

import { useApplyMove, useCatchUpSheet, type CatchUpChoice } from "../../api/parent";
import { ErrorLine, Toggle } from "../ui/Fields";
import { Modal } from "../ui/Modal";
import { PreviewList, dayLabel } from "./PreviewList";

/**
 * "How should Saxon 5/4 catch up?": one card per option, each with its result
 * in plain words; the ones that don't fit say why. Nothing moves until
 * "Catch up".
 */
export function CatchUpSheet({ courseId, onClose }: { courseId: number; onClose: () => void }) {
  const [weekends, setWeekends] = useState(false);
  const sheet = useCatchUpSheet(courseId, weekends);
  const apply = useApplyMove();
  const [picked, setPicked] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const data = sheet.data;
  const choices = data?.choices ?? [];
  const recommended = choices.find((choice) => choice.recommended);
  const chosen: CatchUpChoice | undefined =
    choices.find((choice) => choice.option === picked && choice.workable) ?? recommended;

  return (
    <Modal
      title={data ? `How should ${data.course_name} catch up?` : "Catch up"}
      onClose={onClose}
      wide
      footer={
        done ? (
          <>
            <a className="btn" href="/#/assignments">
              Go to the calendar
            </a>
            <button type="button" className="btn btn-primary" onClick={onClose}>
              Done
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn btn-quiet" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!chosen?.preview || apply.isPending}
              onClick={() =>
                chosen?.preview &&
                apply.mutate(
                  {
                    request: { kind: "catch_up", course_id: courseId, option: chosen.option, allow_weekends: weekends },
                    planHash: chosen.preview.plan_hash,
                  },
                  { onSuccess: (result) => setDone(result.summary) },
                )
              }
            >
              {apply.isPending ? "Moving…" : "Catch up"}
            </button>
          </>
        )
      }
    >
      {sheet.isPending ? <p className="muted">Working out the options…</p> : null}
      <ErrorLine error={sheet.error} />
      {done ? (
        <p className="notice notice-success" role="status">
          Done. {done}
        </p>
      ) : null}
      {data && !done ? (
        <div className="stack-lg">
          <p className="step-lede">
            {data.student_name} is {data.behind} lesson{data.behind === 1 ? "" : "s"} behind
            {data.behind_since ? `, since ${dayLabel(data.behind_since)}` : ""}. There's no single right way to catch up, so
            pick what suits your week. Finished lessons never move.
          </p>
          <fieldset className="choice-cards catch-up-choices">
            <legend className="sr-only">Ways to catch up</legend>
            {choices.map((choice) => (
              <label key={choice.option} className={`choice-card${choice.workable ? "" : " is-unworkable"}`}>
                <input
                  type="radio"
                  name="catch-up"
                  value={choice.option}
                  disabled={!choice.workable}
                  checked={chosen?.option === choice.option}
                  onChange={() => setPicked(choice.option)}
                />
                <span className="choice-title">
                  {choice.label} {choice.recommended ? <span className="badge badge-ready">Recommended</span> : null}
                </span>
                <span className="choice-hint">{choice.description}</span>
                {choice.workable ? (
                  <span className="small">{choice.result}</span>
                ) : (
                  <span className="small muted">Not this time: {choice.why_not}</span>
                )}
              </label>
            ))}
          </fieldset>
          <Toggle
            label="Allow weekends"
            checked={weekends}
            onChange={(value) => {
              setWeekends(value);
              setPicked(null);
            }}
            hint="Lets “Use a day off” put work on a Saturday or Sunday."
          />
          {data.daily_lesson_limit ? (
            <p className="small muted">Your limit is {data.daily_lesson_limit} lessons a day; doubling up stays under it.</p>
          ) : (
            <p className="small muted">No daily lesson limit is set (Settings), so doubling up adds one lesson a day.</p>
          )}
          {chosen?.preview ? (
            <section className="stack" aria-label="What changes">
              <h3 className="section-title">What changes</h3>
              <PreviewList preview={chosen.preview} />
            </section>
          ) : null}
          <ErrorLine error={apply.error} />
        </div>
      ) : null}
    </Modal>
  );
}
