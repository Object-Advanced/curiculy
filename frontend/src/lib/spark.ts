// The daily "Just for fun" puzzle, ported from the legacy app's buildDailySpark
// (static/js/app.js) so a child sees the same puzzle on My work and My trail.
// It is optional play, never a lesson.

export type Spark =
  | { kind: "scramble"; kicker: string; prompt: string; answer: string; hint: string }
  | { kind: "choice"; kicker: string; prompt: string; choices: string[]; answer: string; hint: string; visual?: string }
  | { kind: "think"; kicker: string; prompt: string; answer: string; hint: string };

export interface SparkStudent {
  id: number;
  grade?: string | null;
}

export interface SparkLesson {
  title: string;
  resource_title?: string | null;
  scheduled_date: string;
}

export function mulberry32(seed: number): () => number {
  let state = seed;
  return function rand() {
    let t = (state += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function shuffleCopy<T>(items: T[], rand: () => number): T[] {
  const next = [...items];
  for (let i = next.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1));
    [next[i], next[j]] = [next[j] as T, next[i] as T];
  }
  return next;
}

export function gradeBand(grade: string | null | undefined): "early" | "elem" | "older" {
  const g = String(grade || "").trim().toLowerCase();
  if (!g) return "elem";
  if (/pre-?k|tk|kinder|^k$/.test(g)) return "early";
  const n = Number.parseInt(g, 10);
  if (Number.isFinite(n)) {
    if (n <= 2) return "early";
    if (n <= 5) return "elem";
    return "older";
  }
  return "elem";
}

const SKIP_WORDS = new Set([
  "the", "and", "for", "with", "from", "this", "that", "lesson", "read",
  "chapter", "pages", "page", "week", "unit", "into", "your", "have",
]);

export function puzzleWords(text: string): string[] {
  return String(text || "")
    .split(/[^A-Za-z]+/)
    .map((word) => word.trim())
    .filter((word) => word.length >= 4 && word.length <= 10 && !SKIP_WORDS.has(word.toLowerCase()));
}

const RIDDLES = [
  { prompt: "I have a spine but I’m not a dinosaur. I open, but I’m not a door. What am I?", answer: "a book", hint: "You’re probably holding one later today." },
  { prompt: "The more you take from me, the bigger I get. What am I?", answer: "a hole", hint: "Think about digging." },
  { prompt: "I travel the world but stay in a corner. What am I?", answer: "a stamp", hint: "Mail." },
];

/** Same seed, same day, same child: the same puzzle all day. */
export function buildDailySpark(student: SparkStudent, lessons: SparkLesson[], iso: string): Spark {
  const seed = Number.parseInt(`${student.id}${iso.replaceAll("-", "")}`, 10) || student.id;
  const rand = mulberry32(seed);
  const band = gradeBand(student.grade);
  const titles = lessons
    .filter((item) => item.scheduled_date === iso)
    .map((item) => item.resource_title || item.title)
    .filter(Boolean);
  const source = titles[Math.floor(rand() * Math.max(titles.length, 1))] || "";
  const words = puzzleWords(source);
  const word = words[Math.floor(rand() * Math.max(words.length, 1))] || "";

  if (word && rand() < 0.55) {
    let scrambled = word;
    for (let i = 0; i < 8 && scrambled.toLowerCase() === word.toLowerCase(); i += 1) {
      scrambled = shuffleCopy(word.split(""), rand).join("");
    }
    return {
      kind: "scramble",
      kicker: source ? "From today’s reading" : "Word play",
      prompt: `Unscramble this word: ${scrambled.toUpperCase()}`,
      answer: word,
      hint: source ? `It’s hiding in “${source}.”` : "Sound it out one letter at a time.",
    };
  }

  if (band === "early") {
    const count = 3 + Math.floor(rand() * 5);
    const icon = ["⭐", "🍎", "🌸", "🦆", "🔵"][Math.floor(rand() * 5)] ?? "⭐";
    const choices = shuffleCopy(
      [...new Set([count, count + 1, Math.max(1, count - 1), count + 2])].map(String),
      rand,
    );
    return {
      kind: "choice",
      kicker: "Quick count",
      prompt: "How many do you see?",
      visual: icon.repeat(count),
      choices,
      answer: String(count),
      hint: "Tap each one as you count.",
    };
  }

  if (band === "elem") {
    const a = 4 + Math.floor(rand() * 8);
    const b = 3 + Math.floor(rand() * 7);
    const op = rand() < 0.5 ? "+" : "×";
    const correct = op === "+" ? a + b : a * b;
    const choices = shuffleCopy(
      [...new Set([correct, correct + 1, correct - 1, correct + (op === "+" ? 2 : a)])].map(String),
      rand,
    );
    return {
      kind: "choice",
      kicker: "Warm-up",
      prompt: `What’s ${a} ${op} ${b}?`,
      choices,
      answer: String(correct),
      hint: op === "+" ? "Count up from the first number." : "Think equal groups.",
    };
  }

  const riddle = RIDDLES[Math.floor(rand() * RIDDLES.length)] ?? RIDDLES[0]!;
  return { kind: "think", kicker: "Brain stretch", ...riddle };
}

/** Shared with the legacy My work page (same key, same tab session). */
export function sparkSolvedKey(studentId: number, iso: string): string {
  return `curiculy-spark-${studentId}-${iso}`;
}
