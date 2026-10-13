import { useState } from "react";

import type { Suggestions as SuggestionsData, SuggestedItem } from "../../api/parent";
import { BookCover } from "../library/BookCover";

const ROLE_ORDER = ["textbook", "workbook", "online", "reading", "teacher"];

function ItemLine({ item }: { item: SuggestedItem }) {
  return (
    <span className="row">
      <BookCover
        small
        url={item.entry.cover_url}
        title={item.entry.title}
        kindLabel={item.entry.kind_label}
        subjectCode={item.entry.subject_code}
        kind={item.entry.kind}
      />
      <span>
        <strong>{item.entry.title}</strong>
        <span className="check-why">
          {item.role_label}
          {item.library_item_id ? " · already in your library" : " · added to your library from the catalog"}
        </span>
      </span>
    </span>
  );
}

/**
 * "Other families built a similar curriculum using these…": each combination
 * families used, to start from as it is, with pieces left out, or not at all.
 */
export function Suggestions({
  data,
  busy,
  onUse,
}: {
  data: SuggestionsData;
  busy: boolean;
  onUse: (communityCurriculumId: number, entryIds: number[] | null) => void;
}) {
  const [choosing, setChoosing] = useState<number | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());

  if (data.curricula.length === 0) return null;
  const textbookId = data.textbook?.id;

  return (
    <section className="stack-lg" aria-labelledby="suggestions-title">
      <div>
        <h2 className="section-title" id="suggestions-title">
          Other families built a similar curriculum
        </h2>
        <p className="page-lede">{data.message}</p>
      </div>
      {data.curricula.map((option) => {
        const items = [...option.items].sort((a, b) => ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role));
        const isChoosing = choosing === option.id;
        return (
          <article className="suggestion" key={option.id} aria-label={option.name}>
            <div className="row-between">
              <div>
                <p className="card-title">{option.name}</p>
                <p className="card-meta">
                  Used by {option.families_count} {option.families_count === 1 ? "family" : "families"}
                  {option.days_per_week ? ` · ${option.days_per_week} days a week` : ""}
                </p>
              </div>
              {isChoosing ? null : (
                <div className="row">
                  <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onUse(option.id, null)}>
                    Start from this one
                  </button>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => {
                      setChoosing(option.id);
                      setPicked(new Set(items.map((item) => item.entry.id)));
                    }}
                  >
                    Choose pieces
                  </button>
                </div>
              )}
            </div>
            <ul className="suggestion-items">
              {items.map((item) => (
                <li key={`${item.role}-${item.entry.id}`}>
                  {isChoosing ? (
                    <label>
                      <input
                        type="checkbox"
                        checked={picked.has(item.entry.id)}
                        disabled={item.entry.id === textbookId}
                        onChange={(event) =>
                          setPicked((current) => {
                            const next = new Set(current);
                            if (event.target.checked) next.add(item.entry.id);
                            else next.delete(item.entry.id);
                            return next;
                          })
                        }
                      />
                      <ItemLine item={item} />
                    </label>
                  ) : (
                    <ItemLine item={item} />
                  )}
                </li>
              ))}
            </ul>
            {isChoosing ? (
              <div className="row">
                <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onUse(option.id, [...picked])}>
                  Start with these
                </button>
                <button type="button" className="btn btn-quiet" onClick={() => setChoosing(null)}>
                  Cancel
                </button>
                <span className="field-hint">The textbook always stays. You can add your own books next.</span>
              </div>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}
