"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { LeagueShell } from "@/components/LeagueShell";
import { EditSetupButton } from "@/components/LeagueNav";
import { BasicsForm } from "@/components/setup/BasicsForm";
import { SetupSteps } from "@/components/setup/SetupSteps";
import { type TeamsAction, TeamsForm } from "@/components/setup/TeamsForm";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { type SetupStep, leagueHref, setupHref } from "@/lib/routes";
import type { League, TeamSetup } from "@/lib/types";
import { useLoader } from "@/lib/useLoader";

export default function SetupPage() {
  return (
    <LeagueShell allowSetup>{(league, reload) => <Setup league={league} reload={reload} />}</LeagueShell>
  );
}

function Setup({ league, reload }: { league: League; reload: () => Promise<void> }) {
  const step: SetupStep = useSearchParams().get("step") === "players" ? "players" : "basics";
  const router = useRouter();

  if (league.status === "active") {
    return (
      <div className="card empty-state">
        <h2>This league has been created</h2>
        <p className="muted">
          Teams and players are fixed for the rest of the league. To change them, edit the setup;
          play is paused until you save it again.
        </p>
        <div>
          <EditSetupButton league={league} />
        </div>
      </div>
    );
  }

  return (
    <div className="stack setup">
      <SetupSteps current={step} />
      {step === "basics" ? (
        <BasicsForm
          // Remount with fresh values if the league changes underneath.
          key={league.id}
          initial={league}
          scheduleLocked={league.has_played_matches}
          onSubmit={async (basics) => {
            await api.updateBasics(league.id, basics);
            await reload();
            router.push(setupHref(league.id, "players"));
          }}
        />
      ) : (
        <TeamsStep
          league={league}
          onAction={async (action, teams) => {
            await api.updateTeams(league.id, teams);
            if (action === "back") router.push(setupHref(league.id, "basics"));
            if (action === "create") {
              await api.finalizeSetup(league.id);
              router.push(leagueHref("/league", league.id));
            }
          }}
        />
      )}
    </div>
  );
}

function TeamsStep({
  league,
  onAction,
}: {
  league: League;
  onAction: (action: TeamsAction, teams: TeamSetup[]) => Promise<void>;
}) {
  const { data: teams, error } = useLoader(() => api.listTeams(league.id), [league.id, league.num_teams]);
  if (error) return <ErrorBanner message={error} />;
  if (!teams) return <Loading />;
  return <TeamsForm key={teams.map((t) => t.id).join()} league={league} teams={teams} onAction={onAction} />;
}
