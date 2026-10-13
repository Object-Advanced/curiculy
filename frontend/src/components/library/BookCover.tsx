import { useState } from "react";

import { useImageSource } from "../../api/images";
import { coverColor, coverVariant } from "../../lib/covers";

/**
 * A real cover when there is one (the book lookup's, an approved upload, or
 * the family's own upload); otherwise a generated cover in the subject's
 * color, so the shelf never has a blank.
 */
export function BookCover({
  url,
  title,
  kindLabel,
  subjectCode,
  kind,
  small = false,
}: {
  url: string | null | undefined;
  title: string;
  kindLabel: string;
  subjectCode: string | null | undefined;
  kind: string;
  small?: boolean;
}) {
  const [broken, setBroken] = useState(false);
  const source = useImageSource(url);
  const size = small ? " cover-small" : "";
  if (source && !broken) {
    return (
      <div className={`cover${size}`}>
        <img src={source} alt="" loading="lazy" onError={() => setBroken(true)} />
      </div>
    );
  }
  const design = `cover cover-generated cover-${coverColor(subjectCode, kind)} cover-v${coverVariant(title)}${size}`;
  return (
    <div className={design} aria-hidden="true">
      {/* Too small for a readable title: its first letter instead. */}
      <span className="cover-title">{small ? title.trim().charAt(0).toUpperCase() : title}</span>
      <span className="cover-kind">{kindLabel}</span>
    </div>
  );
}
