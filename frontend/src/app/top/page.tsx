"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

import { fetchJson } from "@/lib/api";

const ExplainabilityCards = dynamic(() => import("@/components/explainability-cards"), {
  loading: () => <p className="text-white/70 mt-4">Loading explainability cards…</p>,
});

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

type AppSettings = {
  fpl_entry_id: number | null;
};

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

export default function TopPage() {
  const [limit, setLimit] = useState(20);
  const [posFilter, setPosFilter] = useState("All");
  const [data, setData] = useState<TopPlayersResponse | null>(null);
  const [explain, setExplain] = useState<ExplainabilityResponse | null>(null);
  const [myTeamIds, setMyTeamIds] = useState<Set<number>>(new Set());
  const [hideInTeam, setHideInTeam] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let canceled = false;

    (async () => {
      try {
        const [topPayload, explainPayload] = await Promise.all([
          fetchJson<TopPlayersResponse>(`${API_BASE}/api/fpl/top?limit=${limit}&compact=true`, {
            cacheMode: "force-cache",
          }),
          fetchJson<ExplainabilityResponse>(
            `${API_BASE}/api/fpl/explainability/top?limit=${Math.min(limit, 20)}&include_next_5=false`,
            { cacheMode: "force-cache" },
          ),
        ]);

        if (canceled) return;
        setData(topPayload);
        setExplain(explainPayload);
        setError(null);
      } catch (e) {
        if (canceled) return;
        setError(e instanceof Error ? e.message : "Failed to load top players");
      }
    })();

    return () => {
      canceled = true;
    };
  }, [limit]);

  useEffect(() => {
    fetchJson<AppSettings>(`${API_BASE}/api/fpl/settings`, { cacheMode: "force-cache" })
      .then(async (s) => {
        if (!s.fpl_entry_id) return;
        try {
          // Avoid expensive import on page load; only read latest recommendation snapshot.
          const rec = await fetchJson<TeamRecommendationLite>(
            `${API_BASE}/api/fpl/team/${s.fpl_entry_id}/recommendation?mode=balanced`,
            { cacheMode: "force-cache" },
          );
          const ids = new Set<number>([
            ...rec.starting_xi.map((p) => p.id),
            ...rec.bench.map((p) => p.id),
          ]);
          setMyTeamIds(ids);
        } catch {
          // ignore
        }
      })
      .catch(() => null);
  }, []);

  const filteredPlayers = useMemo(
    () =>
      (data?.players ?? [])
        .filter((p) => !(hideInTeam && myTeamIds.has(p.id)))
        .filter((p) => posFilter === "All" || p.position === posFilter),
    [data?.players, hideInTeam, myTeamIds, posFilter],
  );

  const filteredExplain = useMemo(
    () =>
      (explain?.players ?? [])
        .filter((p) => !(hideInTeam && myTeamIds.has(p.id)))
        .filter((p) => posFilter === "All" || p.position === posFilter),
    [explain?.players, hideInTeam, myTeamIds, posFilter],
  );

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl sm:text-2xl sm:text-3xl font-black">Research Hub</h1>
          <p className="text-sm text-white/75 mt-1">Top picks + explainability insights in one place.</p>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
          <label className="text-sm text-white/85 flex items-center gap-2">
            <input
              type="checkbox"
              checked={hideInTeam}
              onChange={(e) => setHideInTeam(e.target.checked)}
            />
            Hide in my team
          </label>
          <select
            value={posFilter}
            onChange={(e) => setPosFilter(e.target.value)}
            className="rounded-md h-10 px-3 bg-black/30 border border-white/20 w-full sm:w-auto"
          >
            <option value="All">All Positions</option>
            <option value="GK">Goalkeepers</option>
            <option value="DEF">Defenders</option>
            <option value="MID">Midfielders</option>
            <option value="FWD">Forwards</option>
          </select>
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
            GW {data.next_gw} • Showing {filteredPlayers.length} players
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
                {filteredPlayers.map((p, idx) => {
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

      <ExplainabilityCards
        explain={
          explain
            ? {
                ...explain,
                players: filteredExplain,
              }
            : null
        }
        hideInTeam={hideInTeam}
        myTeamIds={myTeamIds}
      />
    </main>
  );
}
