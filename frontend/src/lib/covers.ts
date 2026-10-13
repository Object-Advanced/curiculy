/** The color of a generated cover: one per subject family, so a shelf reads at a glance. */
export type CoverColor = "sky" | "plum" | "moss" | "clay" | "rose" | "sun" | "ink";

const BY_SUBJECT: Record<string, CoverColor> = {
  math: "sky",
  logic: "sky",
  computer: "sky",
  english: "plum",
  foreign_language: "plum",
  science: "moss",
  health: "moss",
  pe: "moss",
  safety: "moss",
  geography: "clay",
  civics: "clay",
  us_history: "clay",
  world_history: "clay",
  art: "rose",
  music: "rose",
  bible: "sun",
  life_skills: "sun",
};

/** One of three cover designs, picked from the title, so a shelf of one subject still varies. */
export function coverVariant(title: string): 0 | 1 | 2 {
  let hash = 0;
  for (const char of title) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return (hash % 3) as 0 | 1 | 2;
}

export function coverColor(subjectCode: string | null | undefined, kind: string): CoverColor {
  if (subjectCode && BY_SUBJECT[subjectCode]) return BY_SUBJECT[subjectCode];
  return kind === "reading_book" ? "plum" : "ink";
}
