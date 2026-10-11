export function NotFound() {
  return (
    <main className="trail-page">
      <section className="kid-card">
        <h1 className="kid-card-title">This page isn’t here</h1>
        <p className="kid-card-sub">Let’s head back to your trail.</p>
        <a className="kid-btn kid-btn-primary" href="/next/trail">
          Go to My trail
        </a>
      </section>
    </main>
  );
}
