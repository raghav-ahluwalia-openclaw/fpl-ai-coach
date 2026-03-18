"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type Mode = "safe" | "balanced" | "aggressive";

type TargetPlayer = {
  id: number;
  name: string;
  position: string;
  price: number;
  ownership_pct: number;
  expected_points_next_3: number;
  target_score: number;
  tier: string;
  reasons: string[];
};

type TargetsResponse = {
  gameweek: number;
  strategy_mode: Mode;
  horizon: number;
  safe_targets: TargetPlayer[];
  differential_targets: TargetPlayer[];
  summary: string;
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

export default function TargetsPage() {
  const [mode, setMode] = useState<Mode>("balanced");
  const [data, setData] = useState<TargetsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<TargetsResponse>(`${API_BASE}/api/fpl/targets?mode=${mode}&horizon=3&limit=10`)
      .then((payload) => {
        setData(payload);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load targets"));
  }, [mode]);

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
        <h1 className="text-3xl font-black">Target Radar</h1>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as Mode)}
          className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
        >
          <option value="safe">Safe</option>
          <option value="balanced">Balanced</option>
          <option value="aggressive">Aggressive</option>
        </select>
      </div>

      {error ? <p className="text-red-300 mb-3">{error}</p> : null}
      {data ? <p className="text-white/75 mb-4">GW {data.gameweek} • {data.summary}</p> : null}

      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <section className="grid md:grid-cols-2 gap-4">
          <div className={cardClass}>
            <h2 className="font-semibold mb-3 text-[#00ff87]">Safe Targets</h2>
            <ul className="space-y-2">
              {data.safe_targets.map((p) => (
                <li key={`safe-${p.id}`} className="border border-white/15 rounded-md p-3 bg-black/20">
                  <div className="font-medium">{p.name} ({p.position}) • £{p.price.toFixed(1)}</div>
                  <div className="text-sm text-white/75">
                    3GW xP: {p.expected_points_next_3} • Own: {p.ownership_pct}% • Score: {p.target_score}
                  </div>
                  <div className="text-xs text-white/65 mt-1">{p.reasons.join(" • ")}</div>
                </li>
              ))}
            </ul>
          </div>

          <div className={cardClass}>
            <h2 className="font-semibold mb-3 text-pink-200">Differentials</h2>
            <ul className="space-y-2">
              {data.differential_targets.map((p) => (
                <li key={`diff-${p.id}`} className="border border-white/15 rounded-md p-3 bg-black/20">
                  <div className="font-medium">{p.name} ({p.position}) • £{p.price.toFixed(1)}</div>
                  <div className="text-sm text-white/75">
                    3GW xP: {p.expected_points_next_3} • Own: {p.ownership_pct}% • Score: {p.target_score}
                  </div>
                  <div className="text-xs text-white/65 mt-1">{p.reasons.join(" • ")}</div>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </main>
  );
}
