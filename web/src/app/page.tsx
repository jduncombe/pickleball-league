"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LeagueDashboard } from "@/components/LeagueDashboard";
import { LeagueNav } from "@/components/LeagueNav";
import { SetupBanner } from "@/components/SetupBanner";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { Term, a, term } from "@/lib/terms";
import { useLoader } from "@/lib/useLoader";

const STORAGE_KEY = "lastLeague";

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
        <h1>No {term("league", 2)} yet</h1>
        <p className="muted">
          Set up {a("league")} (basics, then {term("team", 2)} and {term("player", 2)}) to generate a
          schedule.
        </p>
        <Link href="/leagues/new" className="button">
          Create {a("league")}
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
          {Term("league")}{" "}
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
      {league.status === "setup" ? (
        <SetupBanner league={league} />
      ) : (
        <LeagueDashboard key={league.id} leagueId={league.id} />
      )}
    </>
  );
}
