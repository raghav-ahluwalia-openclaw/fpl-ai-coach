"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type TopPlayer = {
  id: number;
  name: string;
  position: string;
  price: number;
  xP?: number;
  expected_points?: number;
  form?: number;
  ppg?: number;
};

type AppSettings = { fpl_entry_id: number | null };

type TeamRecommendationLite = {
  starting_xi: Array<{ id: number }>;
  bench: Array<{ id: number }>;
};

type TopPlayersResponse = {
  count: number;
  next_gw: number;
  players: TopPlayer[];
};

type ExplainedPlayer = {
  id: number;
  name: string;
  position: string;
  club?: string;
  price: number;
  xP: number;
  fixture_count: number;
  fixture_badge: "DGW" | "SGW" | "BLANK";
  breakdown: {
    form_score: number;
    fixture_score: number;
    minutes_security: number;
    availability_score: number;
    ownership_risk: number;
    volatility: number;
  };
  next_5_opposition?: Array<{
    gw: number;
    fixtures: Array<{ opponent: string; ha: "H" | "A"; difficulty: number }>;
    is_blank: boolean;
    is_double: boolean;
  }>;
  reason: string;
};

type ExplainabilityResponse = {
  count: number;
  players: ExplainedPlayer[];
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

function safeNum(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function difficultyClass(difficulty: number): string {
  if (difficulty <= 2) return "border-emerald-300/60 text-emerald-200 bg-emerald-500/10";
  if (difficulty === 3) return "border-amber-300/60 text-amber-200 bg-amber-500/10";
  return "border-rose-300/60 text-rose-200 bg-rose-500/10";
}

export default function TopPage() {
  const [limit, setLimit] = useState(20);
  const [data, setData] = useState<TopPlayersResponse | null>(null);
  const [explain, setExplain] = useState<ExplainabilityResponse | null>(null);
  const [myTeamIds, setMyTeamIds] = useState<Set<number>>(new Set());
  const [hideInTeam, setHideInTeam] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<TopPlayersResponse>(`${API_BASE}/api/fpl/top?limit=${limit}`)
      .then((payload) => {
        setData(payload);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load top players"));

    fetchJson<ExplainabilityResponse>(`${API_BASE}/api/fpl/explainability/top?limit=${Math.min(limit, 20)}`)
      .then(setExplain)
      .catch(() => null);
  }, [limit]);

  useEffect(() => {
    fetchJson<AppSettings>(`${API_BASE}/api/fpl/settings`)
      .then(async (s) => {
        if (!s.fpl_entry_id) return;
        await fetchJson(`${API_BASE}/api/fpl/team/${s.fpl_entry_id}/import`, { method: "POST" });
        const rec = await fetchJson<TeamRecommendationLite>(
          `${API_BASE}/api/fpl/team/${s.fpl_entry_id}/recommendation?mode=balanced`,
        );
        const ids = new Set<number>([
          ...rec.starting_xi.map((p) => p.id),
          ...rec.bench.map((p) => p.id),
        ]);
        setMyTeamIds(ids);
      })
      .catch(() => null);
  }, []);

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <h1 className="text-2xl sm:text-2xl sm:text-3xl font-black">Top Picks</h1>
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
          <label className="text-sm text-white/85 flex items-center gap-2">
            <input
              type="checkbox"
              checked={hideInTeam}
              onChange={(e) => setHideInTeam(e.target.checked)}
            />
            Hide players already in my team
          </label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="rounded-md h-10 px-3 bg-black/30 border border-white/20 w-full sm:w-auto"
          >
            <option value={10}>Top 10</option>
            <option value={20}>Top 20</option>
            <option value={30}>Top 30</option>
            <option value={50}>Top 50</option>
          </select>
        </div>
      </div>

      {error ? <p className="text-red-300 mb-3">{error}</p> : null}
      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <section className={cardClass}>
          <p className="text-sm text-white/75 mb-3">
            GW {data.next_gw} • Showing {data.count} players
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-xs md:text-sm">
              <thead>
                <tr className="text-left text-white/70 border-b border-white/10">
                  <th className="py-2">#</th>
                  <th className="py-2">Player</th>
                  <th className="py-2">Pos</th>
                  <th className="py-2">Price</th>
                  <th className="py-2">xP</th>
                  <th className="py-2">Form</th>
                  <th className="py-2">PPG</th>
                </tr>
              </thead>
              <tbody>
                {data.players
                  .filter((p) => !(hideInTeam && myTeamIds.has(p.id)))
                  .map((p, idx) => {
                    const xP = safeNum(p.xP ?? p.expected_points, 0);
                    const form = safeNum(p.form, 0);
                    const ppg = safeNum(p.ppg, 0);
                    const price = safeNum(p.price, 0);
                    const inMyTeam = myTeamIds.has(p.id);

                    return (
                      <tr key={p.id} className={`border-b border-white/5 ${inMyTeam ? "opacity-45" : ""}`}>
                        <td className="py-2">{idx + 1}</td>
                        <td className="py-2 font-medium">{p.name}</td>
                        <td className="py-2">{p.position}</td>
                        <td className="py-2">£{price.toFixed(1)}</td>
                        <td className="py-2 text-[#00ff87] font-semibold">{xP.toFixed(2)}</td>
                        <td className="py-2">{form.toFixed(1)}</td>
                        <td className="py-2">{ppg.toFixed(1)}</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {explain ? (
        <section className={`${cardClass} mt-4`}>
          <h2 className="font-semibold mb-3 text-[#00ff87]">Explainability Cards</h2>
          <div className="grid md:grid-cols-2 gap-3">
            {explain.players
              .filter((p) => !(hideInTeam && myTeamIds.has(p.id)))
              .slice(0, 8)
              .map((p) => (
              <div key={p.id} className={`border border-white/10 rounded-lg p-3 bg-black/20 text-sm ${myTeamIds.has(p.id) ? "opacity-45" : ""}`}>
                <p className="font-semibold">
                  {p.name} <span className="text-white/60">({p.position}{p.club ? ` • ${p.club}` : ""})</span>
                  <span
                    className={`ml-2 text-[11px] rounded-full px-2 py-0.5 border ${
                      p.fixture_badge === "DGW"
                        ? "border-emerald-300 text-emerald-200"
                        : p.fixture_badge === "BLANK"
                          ? "border-rose-300 text-rose-200"
                          : "border-white/30 text-white/80"
                    }`}
                  >
                    {p.fixture_badge}
                  </span>
                </p>
                <p className="text-[#00ff87] font-bold">xP {p.xP.toFixed(2)}</p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-white/80 mt-1">
                  <span>Form: {p.breakdown.form_score.toFixed(1)}</span>
                  <span>Fixture: {p.breakdown.fixture_score.toFixed(1)}</span>
                  <span>Minutes: {p.breakdown.minutes_security.toFixed(1)}</span>
                  <span>Availability: {p.breakdown.availability_score.toFixed(1)}</span>
                </div>

                {p.next_5_opposition?.length ? (
                  <div className="mt-2">
                    <p className="text-xs text-white/65 mb-1">Next 5 GW opposition</p>
                    <div className="space-y-1">
                      {p.next_5_opposition.map((w) => (
                        <div key={`${p.id}-${w.gw}`} className="flex items-center gap-2 flex-wrap">
                          <span className="text-[11px] text-white/60 min-w-[42px]">GW{w.gw}</span>
                          {w.is_blank ? (
                            <span className="text-[11px] rounded-full px-2 py-0.5 border border-white/25 text-white/70">BLANK</span>
                          ) : (
                            w.fixtures.map((f, idx) => (
                              <span
                                key={`${p.id}-${w.gw}-${f.opponent}-${idx}`}
                                className={`text-[11px] rounded-full px-2 py-0.5 border ${difficultyClass(f.difficulty)}`}
                                title={`Difficulty ${f.difficulty}`}
                              >
                                {f.opponent} ({f.ha})
                              </span>
                            ))
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <p className="text-white/65 mt-2">{p.reason}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
