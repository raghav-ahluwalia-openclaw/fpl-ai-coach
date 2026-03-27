"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type AppSettings = { fpl_entry_id: number | null };

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<LivePayload | null>(null);

  useEffect(() => {
    fetchJson<AppSettings>("/api/fpl/settings")
      .then((s) => {
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
        <div className="grid sm:flex gap-2 sm:gap-3 items-center">
          <input
            value={teamId}
            onChange={(e) => setTeamId(e.target.value.replace(/\D/g, ""))}
            placeholder="FPL Team ID"
            inputMode="numeric"
            className="rounded-md h-10 px-3 bg-black/30 border border-white/20 w-full sm:min-w-[220px] sm:w-auto"
          />
          <button
            onClick={() => void load()}
            disabled={loading || !/^\d+$/.test(teamId.trim())}
            className="px-4 h-10 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60 w-full sm:w-auto"
          >
            {loading ? "Refreshing..." : "Refresh Live Score"}
          </button>
        </div>
      </section>

      {error ? <p className="text-red-300 mb-4">{error}</p> : null}

      {data ? (
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
            <p className="text-xs text-white/60 mt-3">Updated: {new Date(data.generated_at).toLocaleString()}</p>
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
            <div className="overflow-x-auto">
              <table className="w-full text-xs md:text-sm">
                <thead>
                  <tr className="text-left text-white/70 border-b border-white/10">
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
                      <td className="py-2 font-medium">{p.name} {p.is_captain ? "(C)" : p.is_vice_captain ? "(VC)" : ""}</td>
                      <td className="py-2">{p.role}</td>
                      <td className="py-2">{p.base_points}</td>
                      <td className="py-2">{p.multiplier}</td>
                      <td className="py-2 font-semibold">{p.live_points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
