"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type LeaguePath, leagueHref } from "@/lib/routes";
import type { League } from "@/lib/types";

export function LeagueNav({ league }: { league: League }) {
  const pathname = usePathname();
  const current = pathname.replace(/\/$/, "") || "/";
  const tabs: { path: LeaguePath; label: string; alsoActiveOn?: string }[] = [
    { path: "/league", label: "Live", alsoActiveOn: "/" },
    { path: "/league/teams", label: "Teams & players" },
    { path: "/league/matches", label: "Schedule & results" },
  ];

  return (
    <div className="league-nav">
      <div>
        <h1>{league.name}</h1>
        <p className="muted">
          {league.num_teams} teams · {league.num_weeks} weeks · {league.rounds_per_week} rounds/week ·{" "}
          {league.num_courts} courts
        </p>
      </div>
      <nav className="tabs">
        {tabs.map((tab) => (
          <Link
            key={tab.path}
            href={leagueHref(tab.path, league.id)}
            className={current === tab.path || current === tab.alsoActiveOn ? "active" : ""}
          >
            {tab.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
