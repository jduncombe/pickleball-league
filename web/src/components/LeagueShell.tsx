"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { api } from "@/lib/api";
import { term } from "@/lib/terms";
import { useLoader } from "@/lib/useLoader";
import type { League } from "@/lib/types";
import { LeagueNav } from "./LeagueNav";
import { SetupBanner } from "./SetupBanner";
import { ErrorBanner, Loading } from "./Status";

type Props = {
  children: (league: League, reload: () => Promise<void>) => React.ReactNode;
  /** Render children even while the league is in setup (the setup page itself). */
  allowSetup?: boolean;
};

/**
 * Loads the league named by `?id=` and renders its header + tabs above
 * `children`. While a league is in setup, other pages show a "continue setup"
 * banner instead.
 */
export function LeagueShell(props: Props) {
  // useSearchParams needs a Suspense boundary in a static export.
  return (
    <Suspense fallback={<Loading />}>
      <LeagueShellInner {...props} />
    </Suspense>
  );
}

function LeagueShellInner({ children, allowSetup = false }: Props) {
  const leagueId = Number(useSearchParams().get("id"));
  const { data: league, error, reload } = useLoader(
    () => (leagueId ? api.getLeague(leagueId) : Promise.reject(new Error(`No ${term("league")} selected`))),
    [leagueId],
  );

  if (error) return <ErrorBanner message={error} />;
  if (!league) return <Loading />;
  return (
    <>
      <LeagueNav league={league} />
      {league.status === "setup" && !allowSetup ? <SetupBanner league={league} /> : children(league, reload)}
    </>
  );
}
