import { dayOf, seasonOf, type Season } from "./dates";

export type StickerIcon =
  | "star" | "book" | "leaf" | "pencil" | "globe" | "palette" | "note" | "heart"
  | "acorn" | "apple" | "owl" | "pumpkin" | "snowflake" | "mitten" | "flower"
  | "kite" | "sun" | "shell" | "moon" | "tree";

/** Sticker backgrounds are tokens (tokens.css, kid persona). */
export type StickerTone = "sun" | "grape" | "rose" | "leaf" | "sky" | "peach" | "cream";

export interface Sticker {
  icon: StickerIcon;
  tone: StickerTone;
  label: string;
}

interface LessonLike {
  title: string;
  subject_name?: string | null;
  resource_title?: string | null;
}

const LESSON_STICKERS: { test: RegExp; sticker: Sticker }[] = [
  { test: /math|saxon|fraction|algebra|geometr|count|number|multipl|divis|arith/i, sticker: { icon: "star", tone: "sun", label: "Math" } },
  { test: /writ|spell|grammar|handwrit|copywork|journal|essay|vocab/i, sticker: { icon: "pencil", tone: "rose", label: "Writing" } },
  { test: /read|book|novel|chapter|literat|phonics|story|poem/i, sticker: { icon: "book", tone: "grape", label: "Reading" } },
  { test: /scien|nature|biolog|chemi|physic|astronom|plant|animal|matter|weather/i, sticker: { icon: "leaf", tone: "leaf", label: "Science" } },
  { test: /histor|geograph|social|civic|map|world/i, sticker: { icon: "globe", tone: "sky", label: "History" } },
  { test: /\bart\b|draw|paint|craft|sketch/i, sticker: { icon: "palette", tone: "peach", label: "Art" } },
  { test: /music|piano|sing|instrument|violin|guitar/i, sticker: { icon: "note", tone: "grape", label: "Music" } },
];

const DEFAULT_STICKER: Sticker = { icon: "star", tone: "cream", label: "Star" };

/** The sticker a finished lesson earns, picked from its subject, book, or title. */
export function lessonSticker(lesson: LessonLike): Sticker {
  for (const text of [lesson.subject_name, lesson.resource_title, lesson.title]) {
    if (!text) continue;
    const match = LESSON_STICKERS.find((entry) => entry.test.test(text));
    if (match) return match.sticker;
  }
  return DEFAULT_STICKER;
}

export const SEASON_COLLECTIONS: Record<Season, Sticker[]> = {
  autumn: [
    { icon: "acorn", tone: "sun", label: "Acorn" },
    { icon: "leaf", tone: "peach", label: "Maple leaf" },
    { icon: "apple", tone: "rose", label: "Apple" },
    { icon: "owl", tone: "grape", label: "Owl" },
    { icon: "pumpkin", tone: "peach", label: "Pumpkin" },
    { icon: "moon", tone: "sky", label: "Harvest moon" },
    { icon: "book", tone: "cream", label: "Cozy book" },
    { icon: "star", tone: "sun", label: "Shooting star" },
  ],
  winter: [
    { icon: "snowflake", tone: "sky", label: "Snowflake" },
    { icon: "mitten", tone: "rose", label: "Mitten" },
    { icon: "tree", tone: "leaf", label: "Pine tree" },
    { icon: "moon", tone: "grape", label: "Winter moon" },
    { icon: "owl", tone: "cream", label: "Snowy owl" },
    { icon: "heart", tone: "rose", label: "Warm heart" },
    { icon: "star", tone: "sun", label: "North star" },
    { icon: "book", tone: "grape", label: "Fireside book" },
  ],
  spring: [
    { icon: "flower", tone: "rose", label: "Tulip" },
    { icon: "kite", tone: "sky", label: "Kite" },
    { icon: "leaf", tone: "leaf", label: "New leaf" },
    { icon: "heart", tone: "rose", label: "Ladybug heart" },
    { icon: "sun", tone: "sun", label: "Spring sun" },
    { icon: "apple", tone: "leaf", label: "Apple blossom" },
    { icon: "star", tone: "cream", label: "Bright star" },
    { icon: "book", tone: "grape", label: "Garden book" },
  ],
  summer: [
    { icon: "sun", tone: "sun", label: "Sunshine" },
    { icon: "shell", tone: "peach", label: "Seashell" },
    { icon: "kite", tone: "sky", label: "Beach kite" },
    { icon: "flower", tone: "rose", label: "Sunflower" },
    { icon: "tree", tone: "leaf", label: "Shady tree" },
    { icon: "star", tone: "sun", label: "Firefly" },
    { icon: "moon", tone: "grape", label: "Summer moon" },
    { icon: "heart", tone: "rose", label: "Picnic heart" },
  ],
};

/** The seasonal sticker for reaching camp today. */
export function campPrize(iso: string): Sticker {
  const collection = SEASON_COLLECTIONS[seasonOf(iso)];
  return collection[(dayOf(iso) - 1) % collection.length] ?? DEFAULT_STICKER;
}

export const BONUS_STICKER: Sticker = { icon: "star", tone: "sun", label: "Bonus" };
