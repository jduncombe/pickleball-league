import Link from "next/link";

export function Nav() {
  return (
    <header className="nav">
      <Link href="/" className="brand">
        🥒 Pickleball League
      </Link>
      <nav>
        <Link href="/">Dashboard</Link>
        <Link href="/leagues">Leagues</Link>
        <Link href="/leagues/new" className="button small">
          New league
        </Link>
      </nav>
    </header>
  );
}
