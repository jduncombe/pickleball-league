"use client";

import { useRouter } from "next/navigation";
import { BasicsForm, DEFAULT_BASICS } from "@/components/setup/BasicsForm";
import { SetupSteps } from "@/components/setup/SetupSteps";
import { api } from "@/lib/api";
import { setupHref } from "@/lib/routes";

/** Setup step 1 for a new league; step 2 is /league/setup/?step=players. */
export default function NewLeaguePage() {
  const router = useRouter();
  return (
    <div className="stack setup">
      <h1>New league</h1>
      <SetupSteps current="basics" />
      <BasicsForm
        initial={DEFAULT_BASICS}
        onSubmit={async (basics) => {
          const league = await api.createLeague(basics);
          router.push(setupHref(league.id, "players"));
        }}
      />
    </div>
  );
}
