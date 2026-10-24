import type { TeamRef } from "@/lib/types";

export const DUPR_READY_TITLE = "All players have DUPR IDs";

/**
 * A team's display name. With `showDupr`, teams whose players all have DUPR
 * IDs get the DUPR colour (see the legend on the live view).
 */
export function TeamName({
  team,
  showDupr = false,
  className = "",
}: {
  team: TeamRef;
  showDupr?: boolean;
  className?: string;
}) {
  const dupr = showDupr && team.dupr_ready;
  return (
    <strong className={`${className} ${dupr ? "dupr" : ""}`.trim() || undefined} title={dupr ? DUPR_READY_TITLE : undefined}>
      {team.display_name}
    </strong>
  );
}

export function DuprLegend() {
  return (
    <span className="legend">
      <span className="dupr-swatch" aria-hidden="true" /> {DUPR_READY_TITLE}
    </span>
  );
}
