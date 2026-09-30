"use client";

import Link from "next/link";
import { ErrorBanner, Loading } from "@/components/Status";
import { api } from "@/lib/api";
import { leagueHref } from "@/lib/routes";
import { useLoader } from "@/lib/useLoader";

export default function LeaguesPage() {
  const { data: leagues, error } = useLoader(() => api.listLeagues());

  return (
    <div className="stack">
      <div className="toolbar">
        <h1>Leagues</h1>
        <Link href="/leagues/new" className="button">
          New league
        </Link>
      </div>
      <ErrorBanner message={error} />
      {!leagues ? (
        !error && <Loading />
      ) : leagues.length === 0 ? (
        <p className="muted">No leagues yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Teams</th>
              <th>Weeks</th>
              <th>Rounds / week</th>
              <th>Courts</th>
              <th>Current week</th>
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
                <td>{l.rounds_per_week}</td>
                <td>{l.num_courts}</td>
                <td>{l.current_week}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
