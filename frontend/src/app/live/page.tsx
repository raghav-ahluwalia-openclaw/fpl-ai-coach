"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { fetchJson } from "@/lib/api";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui-state";

type AppSettings = {
  fpl_entry_id: number | null;
  entry_name?: string | null;
  player_name?: string | null;
};

type LivePlayer = {
  id: number;
  name: string;
  position: number;
  role: "starter" | "bench";
  multiplier: number;
  base_points: number;
  live_points: number;
  is_captain: boolean;
  is_vice_captain: boolean;
};

type LivePayload = {
  entry_id: number;
  gameweek: number;
  generated_at: string;
  live_summary: {
    total_live_points: number;
    starters_live_points: number;
    bench_live_points: number;
  };
  captain: { name: string; base_points: number; multiplier: number; live_points: number } | null;
  vice_captain: { name: string; base_points: number; multiplier: number; live_points: number } | null;
  players: LivePlayer[];
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

export default function LivePage() {
  const [teamId, setTeamId] = useState("");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LivePayload | null>(null);

  useEffect(() => {
    fetchJson<AppSettings>("/api/fpl/settings")
      .then((s) => {
        setSettings(s);
        if (s.fpl_entry_id) setTeamId(String(s.fpl_entry_id));
      })
      .catch(() => null);
  }, []);

  const load = useCallback(async (idOverride?: string) => {
    const id = (idOverride ?? teamId).trim();
    if (!/^\d+$/.test(id)) {
      setError("Team ID must be numeric.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchJson<LivePayload>(`/api/fpl/team/${id}/live`);
      setData(payload);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load live team view");
    } finally {
      setLoading(false);
    }
  }, [teamId]);

  useEffect(() => {
    if (/^\d+$/.test(teamId)) {
      void load(teamId);
    }
  }, [teamId, load]);

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-2xl sm:text-3xl font-black mb-4">Live Team View</h1>

      <section className={`${cardClass} mb-4`}>
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <div>
            {settings?.fpl_entry_id ? (
              <div className="flex flex-col">
                <span className="text-xs text-white/75 uppercase tracking-wider font-bold">FPL Team</span>
                <span className="text-lg font-bold text-[#00ff87]">
                  {settings.entry_name || `Entry #${settings.fpl_entry_id}`}
                </span>
                {settings.player_name && (
                  <span className="text-sm text-white/80 italic">{settings.player_name}</span>
                )}
                {data?.generated_at && (
                  <span className="text-[10px] text-white/65 mt-1 uppercase font-medium">
                    Updated: {new Date(data.generated_at).toLocaleString(undefined, { timeZoneName: "short" })}
                  </span>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 text-amber-300">
                <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current">
                  <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
                </svg>
                <p className="text-sm font-medium">
                  Team ID not set. Please configure it in the{" "}
                  <Link href="/settings" className="underline hover:text-amber-200">
                    Settings
                  </Link>{" "}
                  page.
                </p>
              </div>
            )}
          </div>
          <div className="flex gap-2 w-full sm:w-auto mt-2 sm:mt-0">
            {settings?.fpl_entry_id && (
              <button
                onClick={() => void load()}
                disabled={loading}
                className="h-10 w-10 grid place-items-center rounded-full border border-white/30 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87] transition disabled:opacity-60"
                aria-label="Refresh live score"
                title={loading ? "Refreshing..." : "Refresh live score"}
              >
                {loading ? (
                  <svg className="animate-spin h-5 w-5 text-current" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
                    <path
                      d="M20 12a8 8 0 1 1-2.34-5.66M20 4v6h-6"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
              </button>
            )}
          </div>
        </div>
      </section>

      {error ? (
        <div className="mb-4">
          <ErrorState message={error} onRetry={() => void load()} />
        </div>
      ) : null}

      {loading && !data ? (
        <LoadingState label="Loading live team data..." />
      ) : data ? (
        <div className="grid gap-4">
          <section className={cardClass}>
            <p className="text-sm text-white/75 mb-2">Entry #{data.entry_id} • GW {data.gameweek}</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-sm">
              <div className="rounded-md border border-white/10 bg-black/20 p-3">
                <p className="text-white/70">Live total</p>
                <p className="text-2xl font-bold text-[#00ff87]">{data.live_summary.total_live_points}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-black/20 p-3">
                <p className="text-white/70">Starters</p>
                <p className="text-xl font-semibold">{data.live_summary.starters_live_points}</p>
              </div>
              <div className="rounded-md border border-white/10 bg-black/20 p-3">
                <p className="text-white/70">Bench</p>
                <p className="text-xl font-semibold">{data.live_summary.bench_live_points}</p>
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Captain impact</h2>
            <p className="text-sm text-white/85">
              C: <strong>{data.captain?.name || "—"}</strong> ({data.captain?.base_points ?? 0} x {data.captain?.multiplier ?? 0} = {data.captain?.live_points ?? 0})
              {" • "}
              VC: <strong>{data.vice_captain?.name || "—"}</strong>
            </p>
          </section>

          <section className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Live player breakdown</h2>
            <div className="overflow-x-auto focus-visible:outline-none" tabIndex={0} role="region" aria-label="Live player breakdown table">
              <table className="w-full text-xs md:text-sm">
                <thead>
                  <tr className="text-left text-white/85 border-b border-white/10">
                    <th className="py-2">Player</th>
                    <th className="py-2">Role</th>
                    <th className="py-2">Base</th>
                    <th className="py-2">Mult</th>
                    <th className="py-2">Live</th>
                  </tr>
                </thead>
                <tbody>
                  {data.players.map((p) => (
                    <tr key={`${p.id}-${p.position}`} className="border-b border-white/5">
                      <td className="py-2 font-medium text-white">{p.name} {p.is_captain ? "(C)" : p.is_vice_captain ? "(VC)" : ""}</td>
                      <td className="py-2 text-white/90">{p.role}</td>
                      <td className="py-2 text-white/90">{p.base_points}</td>
                      <td className="py-2 text-white/90">{p.multiplier}</td>
                      <td className="py-2 font-bold text-white">{p.live_points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      ) : !loading && !error && settings?.fpl_entry_id ? (
        <EmptyState 
          title="No live data available yet" 
          description="Live data might not be available before the gameweek deadline passes."
          onRetry={() => void load()}
        />
      ) : null}
    </main>
  );
}
