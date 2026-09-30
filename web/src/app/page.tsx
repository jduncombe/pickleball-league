"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LeagueDashboard } from "@/components/LeagueDashboard";
import { LeagueNav } from "@/components/LeagueNav";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { useLoader } from "@/lib/useLoader";

const STORAGE_KEY = "pickleball:lastLeague";

/** Default screen: the live board for the last-viewed (or newest) league. */
export default function HomePage() {
  const { data: leagues, error } = useLoader(() => api.listLeagues());
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    if (!leagues?.length) return;
    let remembered: number | null = null;
    try {
      remembered = Number(localStorage.getItem(STORAGE_KEY)) || null;
    } catch {
      // storage unavailable (private mode etc.)
    }
    const valid = leagues.some((l) => l.id === remembered);
    setSelected(valid ? remembered : leagues[0].id);
  }, [leagues]);

  function choose(id: number) {
    setSelected(id);
    try {
      localStorage.setItem(STORAGE_KEY, String(id));
    } catch {}
  }

  if (error) return <ErrorBanner message={error} />;
  if (!leagues) return <Loading />;
  if (leagues.length === 0) {
    return (
      <div className="empty">
        <h1>No leagues yet</h1>
        <p className="muted">Create a league to generate teams and a round-robin schedule.</p>
        <Link href="/leagues/new" className="button">
          Create a league
        </Link>
      </div>
    );
  }

  const league = leagues.find((l) => l.id === selected);
  if (!league) return <Loading />;

  return (
    <>
      {leagues.length > 1 && (
        <label className="league-picker">
          League{" "}
          <select value={league.id} onChange={(e) => choose(Number(e.target.value))}>
            {leagues.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <LeagueNav league={league} />
      <LeagueDashboard key={league.id} leagueId={league.id} />
    </>
  );
}
