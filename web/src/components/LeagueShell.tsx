"use client";

import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useLoader } from "@/lib/useLoader";
import type { League } from "@/lib/types";
import { LeagueNav } from "./LeagueNav";
import { ErrorBanner, Loading } from "./Status";

/** Loads the league from the route's [id] and renders its header + tabs above `children`. */
export function LeagueShell({ children }: { children: (league: League) => React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const leagueId = Number(id);
  const { data: league, error } = useLoader(() => api.getLeague(leagueId), [leagueId]);

  if (error) return <ErrorBanner message={error} />;
  if (!league) return <Loading />;
  return (
    <>
      <LeagueNav league={league} />
      {children(league)}
    </>
  );
}
