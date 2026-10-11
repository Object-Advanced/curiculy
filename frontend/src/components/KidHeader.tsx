import { Link } from "react-router";

export type KidPage = "trail" | "journal";

interface KidHeaderProps {
  name: string;
  line: string;
  current: KidPage;
  /** A parent previewing goes back to the Kids page, a child to My work. */
  backHref: string;
  backLabel: string;
  /** Keeps a parent's chosen child (`?student=`) between kid pages. */
  search: string;
}

export function KidHeader({ name, line, current, backHref, backLabel, search }: KidHeaderProps) {
  const tab = (page: KidPage, label: string) => (
    <Link
      to={{ pathname: `/${page}`, search }}
      aria-current={current === page ? "page" : undefined}
      className={`kid-tab${current === page ? " kid-tab-active" : ""}`}
    >
      {label}
    </Link>
  );
  return (
    <header className="kid-header">
      <nav aria-label="Pages" className="kid-tabs">
        <a href={backHref} className="kid-tab">
          {backLabel}
        </a>
        {tab("trail", "My trail")}
        {tab("journal", "Sticker journal")}
      </nav>
      <div className="kid-hello">
        <h1 className="kid-hello-title">Hi {name}!</h1>
        <p className="kid-hello-line">{line}</p>
      </div>
    </header>
  );
}

/** "2 stops to camp", "You made it to camp!", or a rest day. */
export function trailLine(total: number, done: number): string {
  const left = total - done;
  if (!total) return "No stops today. It’s a rest day at camp.";
  if (left === 0) return "You made it to camp!";
  return `${left} ${left === 1 ? "stop" : "stops"} to camp`;
}
