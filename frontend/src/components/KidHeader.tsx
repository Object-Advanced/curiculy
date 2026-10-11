interface KidHeaderProps {
  name: string;
  total: number;
  done: number;
  /** A parent previewing a child's trail goes back to the Kids page, a child to My work. */
  backHref: string;
  backLabel: string;
}

export function KidHeader({ name, total, done, backHref, backLabel }: KidHeaderProps) {
  const left = total - done;
  const line = !total
    ? "No stops today. It’s a rest day at camp."
    : left === 0
      ? "You made it to camp!"
      : `${left} ${left === 1 ? "stop" : "stops"} to camp`;
  return (
    <header className="kid-header">
      <nav aria-label="Pages" className="kid-tabs">
        <a href={backHref} className="kid-tab">
          {backLabel}
        </a>
        <a href="/next/trail" aria-current="page" className="kid-tab kid-tab-active">
          My trail
        </a>
      </nav>
      <div className="kid-hello">
        <h1 className="kid-hello-title">Hi {name}!</h1>
        <p className="kid-hello-line">{line}</p>
      </div>
    </header>
  );
}
