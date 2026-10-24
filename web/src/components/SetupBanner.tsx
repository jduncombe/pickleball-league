import Link from "next/link";
import { setupHref } from "@/lib/routes";
import type { League } from "@/lib/types";

/** Shown instead of play screens while a league is in setup. */
export function SetupBanner({ league }: { league: League }) {
  const firstTime = league.created_league_at === null;
  return (
    <div className="card empty-state">
      <h2>{firstTime ? "This league is being set up" : "This league's setup is being edited"}</h2>
      <p className="muted">
        {firstTime
          ? "Enter the teams and players, then create the league to generate the schedule."
          : "Play is paused until the setup is saved."}
      </p>
      <div>
        <Link href={setupHref(league.id, firstTime ? "players" : "basics")} className="button">
          Continue setup
        </Link>
      </div>
    </div>
  );
}
