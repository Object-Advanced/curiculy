import { useId, useState, type FormEvent } from "react";

import type { Spark } from "../lib/spark";

interface BonusChestProps {
  spark: Spark;
  solved: boolean;
  onSolved: () => void;
}

/** The daily puzzle behind the bonus chest. Optional play, never a lesson. */
export function BonusChest({ spark, solved, onSolved }: BonusChestProps) {
  const [open, setOpen] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [showHint, setShowHint] = useState(false);
  const regionId = useId();

  const check = (guess: string) => {
    if (guess.trim().toLowerCase() === spark.answer.toLowerCase()) {
      setFeedback(`Nice: ${spark.answer}. Bonus sticker!`);
      onSolved();
    } else {
      setFeedback("Try once more. You’ve got this.");
    }
  };

  const submitGuess = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    check(String(data.get("guess") ?? ""));
  };

  return (
    <section className="kid-card bonus-chest" aria-labelledby={`${regionId}-title`}>
      <div className="bonus-head">
        <div>
          <p className="kid-kicker">Just for fun</p>
          <h2 id={`${regionId}-title`} className="kid-card-title">
            Bonus chest
          </h2>
        </div>
        <button
          type="button"
          className="kid-btn kid-btn-quiet"
          aria-expanded={open}
          aria-controls={regionId}
          onClick={() => setOpen((value) => !value)}
        >
          {solved ? "See puzzle" : open ? "Close" : "Open it"}
        </button>
      </div>
      {solved && !open && <p className="kid-card-sub">Solved! The bonus sticker is yours.</p>}
      <div id={regionId} hidden={!open} className="bonus-body">
        <p className="kid-kicker">{spark.kicker}</p>
        <p className="bonus-prompt">{spark.prompt}</p>
        {spark.kind === "choice" && spark.visual && (
          <p className="bonus-visual" aria-hidden="true">
            {spark.visual}
          </p>
        )}
        {spark.kind === "choice" && (
          <div className="bonus-choices">
            {spark.choices.map((choice) => (
              <button key={choice} type="button" className="kid-btn" disabled={solved} onClick={() => check(choice)}>
                {choice}
              </button>
            ))}
          </div>
        )}
        {spark.kind === "scramble" && (
          <form className="bonus-guess" onSubmit={submitGuess}>
            <label className="sr-only" htmlFor={`${regionId}-guess`}>
              Your guess
            </label>
            <input
              id={`${regionId}-guess`}
              name="guess"
              maxLength={24}
              autoComplete="off"
              disabled={solved}
              defaultValue={solved ? spark.answer : ""}
            />
            <button type="submit" className="kid-btn kid-btn-primary" disabled={solved}>
              Check
            </button>
          </form>
        )}
        {spark.kind === "think" && !solved && (
          <button type="button" className="kid-btn" onClick={() => check(spark.answer)}>
            Show me
          </button>
        )}
        <p className="bonus-feedback" role="status">
          {solved && !feedback ? `Solved: ${spark.answer}.` : feedback}
        </p>
        {!solved && (
          <>
            <button type="button" className="kid-link" onClick={() => setShowHint(true)} hidden={showHint}>
              Need a hint?
            </button>
            {showHint && <p className="bonus-hint">{spark.hint}</p>}
          </>
        )}
      </div>
    </section>
  );
}
