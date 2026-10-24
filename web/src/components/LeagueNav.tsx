"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { type LeaguePath, leagueHref, setupHref } from "@/lib/routes";
import { Term, count, term } from "@/lib/terms";
import type { League } from "@/lib/types";

export function LeagueNav({ league }: { league: League }) {
  const pathname = usePathname();
  const current = pathname.replace(/\/$/, "") || "/";
  const inSetup = league.status === "setup";
  const tabs: { path: LeaguePath; label: string; alsoActiveOn?: string }[] = [
    { path: "/league", label: "Live", alsoActiveOn: "/" },
    { path: "/league/teams", label: `${Term("team", 2)} & ${term("player", 2)}` },
    { path: "/league/matches", label: "Schedule & results" },
  ];
  if (inSetup) tabs.push({ path: "/league/setup", label: "Setup" });

  return (
    <div className="league-nav">
      <div>
        <h1>
          {league.name} {inSetup && <span className="badge">in setup</span>}
        </h1>
        <p className="muted">
          {count(league.num_teams, "team")} · {count(league.num_weeks, "week")} ·{" "}
          {count(league.matches_per_week, "match")}/{term("week")} · {count(league.num_courts, "court")} ·{" "}
          {term("game", 2)} to {league.points_to_win}
        </p>
      </div>
      <div className="league-nav-actions">
        <nav className="tabs">
          {tabs.map((tab) => (
            <Link
              key={tab.path}
              href={tab.path === "/league/setup" ? setupHref(league.id, "basics") : leagueHref(tab.path, league.id)}
              className={current === tab.path || current === tab.alsoActiveOn ? "active" : ""}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
        {!inSetup && <EditSetupButton league={league} />}
      </div>
    </div>
  );
}

/** Puts an active league back into setup, after confirming, and opens setup. */
export function EditSetupButton({ league }: { league: League }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function edit() {
    const shape = `the number of ${term("team", 2)}, ${term("week", 2)} or ${term("match", 2)} per ${term("week")}`;
    const ok = window.confirm(
      `Edit the ${term("league")} setup?\n\nPlay is paused until you finish editing. ` +
        (league.has_played_matches
          ? `${Term("match", 2)} have been played, so names, ${term("player", 2)} and ${term("court", 2)} can change, but not ${shape} or the points to win.`
          : `Changing ${shape} rebuilds the schedule.`),
    );
    if (!ok) return;
    setBusy(true);
    try {
      await api.editSetup(league.id);
      router.push(setupHref(league.id, "basics"));
    } catch (err) {
      window.alert(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <button type="button" className="secondary small" disabled={busy} onClick={edit}>
      Edit setup
    </button>
  );
}
