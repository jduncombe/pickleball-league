"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { League } from "@/lib/types";

export function LeagueNav({ league }: { league: League }) {
  const pathname = usePathname();
  const base = `/leagues/${league.id}`;
  const tabs: { href: string; label: string; alsoActiveOn?: string }[] = [
    { href: base, label: "Live", alsoActiveOn: "/" },
    { href: `${base}/teams`, label: "Teams & players" },
    { href: `${base}/matches`, label: "Schedule & results" },
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
          <Link key={tab.href} href={tab.href} className={pathname === tab.href || pathname === tab.alsoActiveOn ? "active" : ""}>
            {tab.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
