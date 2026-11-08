"use client";

import Link from "next/link";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { leagueHref, setupHref } from "@/lib/routes";
import { Term, term } from "@/lib/terms";
import { useLoader } from "@/lib/useLoader";

export default function LeaguesPage() {
  const { data: leagues, error } = useLoader(() => api.listLeagues());
  const { user } = useAuth();

  return (
    <div className="stack">
      <div className="toolbar">
        <h1>{Term("league", 2)}</h1>
        <Link href="/leagues/new" className="button">
          New {term("league")}
        </Link>
      </div>
      <ErrorBanner message={error} />
      {!leagues ? (
        !error && <Loading />
      ) : leagues.length === 0 ? (
        <p className="muted">No {term("league", 2)} yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>{Term("team", 2)}</th>
              <th>{Term("week", 2)}</th>
              <th>
                {Term("match", 2)} / {term("week")}
              </th>
              <th>{Term("court", 2)}</th>
              <th>Current {term("week")}</th>
              <th>Status</th>
              <th>Owner</th>
            </tr>
          </thead>
          <tbody>
            {leagues.map((l) => (
              <tr key={l.id}>
                <td>
                  <Link href={leagueHref("/league", l.id)}>{l.name}</Link>
                </td>
                <td>{l.num_teams}</td>
                <td>{l.num_weeks}</td>
                <td>{l.matches_per_week}</td>
                <td>{l.num_courts}</td>
                <td>{l.current_week}</td>
                <td>
                  {l.status === "setup" ? <Link href={setupHref(l.id, "basics")}>In setup</Link> : "Active"}
                </td>
                <td className="muted">{l.owner?.id === user?.id ? "You" : (l.owner?.name ?? "–")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
