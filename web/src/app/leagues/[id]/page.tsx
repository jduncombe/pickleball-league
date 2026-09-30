"use client";

import { LeagueDashboard } from "@/components/LeagueDashboard";
import { LeagueShell } from "@/components/LeagueShell";

export default function LeagueLivePage() {
  return <LeagueShell>{(league) => <LeagueDashboard leagueId={league.id} />}</LeagueShell>;
}
