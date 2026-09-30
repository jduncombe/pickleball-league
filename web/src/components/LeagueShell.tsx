"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { api } from "@/lib/api";
import { useLoader } from "@/lib/useLoader";
import type { League } from "@/lib/types";
import { LeagueNav } from "./LeagueNav";
import { ErrorBanner, Loading } from "./Status";

type Props = { children: (league: League) => React.ReactNode };

/** Loads the league named by `?id=` and renders its header + tabs above `children`. */
export function LeagueShell(props: Props) {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense fallback={<Loading />}>
      <LeagueShellInner {...props} />
    </Suspense>
  );
}

function LeagueShellInner({ children }: Props) {
  const leagueId = Number(useSearchParams().get("id"));
  const { data: league, error } = useLoader(
    () => (leagueId ? api.getLeague(leagueId) : Promise.reject(new Error("No league selected"))),
    [leagueId],
  );

  if (error) return <ErrorBanner message={error} />;
  if (!league) return <Loading />;
  return (
    <>
      <LeagueNav league={league} />
      {children(league)}
    </>
  );
}
