"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { type LeaguePath, leagueHref, setupHref } from "@/lib/routes";
import type { League } from "@/lib/types";

const plural = (n: number, word: string, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;

export function LeagueNav({ league }: { league: League }) {
  const pathname = usePathname();
  const current = pathname.replace(/\/$/, "") || "/";
  const inSetup = league.status === "setup";
  const tabs: { path: LeaguePath; label: string; alsoActiveOn?: string }[] = [
    { path: "/league", label: "Live", alsoActiveOn: "/" },
    { path: "/league/teams", label: "Teams & players" },
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
          {league.num_teams} teams · {plural(league.num_weeks, "week")} ·{" "}
          {plural(league.matches_per_week, "match", "matches")}/week · {plural(league.num_courts, "court")} ·
          games to {league.points_to_win}
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
    const ok = window.confirm(
      "Edit the league setup?\n\nPlay is paused until you finish editing. " +
        (league.has_played_matches
          ? "Matches have been played, so names, players and courts can change, but not the number of teams, weeks or rounds."
          : "Changing the number of teams, weeks or rounds rebuilds the schedule."),
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
