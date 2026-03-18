"use client";

import { useState } from "react";

import { fetchJson } from "@/lib/api";

type Mode = "safe" | "balanced" | "aggressive";

type Pick = {
  id: number;
  name: string;
  position: string;
  price: number;
  expected_points: number;
  reason: string;
};

type TeamRecommendation = {
  entry_id: number;
  gameweek: number;
  strategy_mode: Mode;
  formation: string;
  starting_xi: Pick[];
  bench: Pick[];
  captain: string;
  vice_captain: string;
  transfer_out: string;
  transfer_in: string;
  transfer_reason: string;
  bank: number;
  squad_value: number;
  confidence: number;
  summary: string;
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

export default function TeamPage() {
  const [teamId, setTeamId] = useState("");
  const [mode, setMode] = useState<Mode>("balanced");
  const [data, setData] = useState<TeamRecommendation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const normalizedTeamId = teamId.trim();
  const teamIdValid = /^\d+$/.test(normalizedTeamId);

  async function run() {
    if (!normalizedTeamId || !teamIdValid) {
      setError("Team ID must be numeric.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await fetchJson<{ ok: boolean }>(`${API_BASE}/api/fpl/team/${normalizedTeamId}/import`, { method: "POST" });
      const recommendation = await fetchJson<TeamRecommendation>(
        `${API_BASE}/api/fpl/team/${normalizedTeamId}/recommendation?mode=${mode}`,
      );
      setData(recommendation);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load team recommendation");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-3xl font-black mb-4">My Team</h1>

      <section className={`${cardClass} mb-6`}>
        <div className="flex gap-3 flex-wrap items-center">
          <input
            value={teamId}
            onChange={(e) => setTeamId(e.target.value.replace(/\D/g, ""))}
            placeholder="FPL Team ID"
            inputMode="numeric"
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20 min-w-[220px]"
          />
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as Mode)}
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
          >
            <option value="safe">Safe</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
          <button
            onClick={run}
            disabled={loading || !normalizedTeamId || !teamIdValid}
            className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60"
          >
            {loading ? "Loading..." : "Analyze Team"}
          </button>
        </div>
        {teamId && !teamIdValid ? <p className="text-amber-200 text-sm mt-2">Team ID should contain digits only.</p> : null}
      </section>

      {error ? <p className="text-red-300 mb-4">{error}</p> : null}

      {data ? (
        <section className={cardClass}>
          <p className="text-sm text-white/75 mb-2">
            Entry #{data.entry_id} • GW {data.gameweek} • {data.formation} • {data.strategy_mode.toUpperCase()} • Confidence {(data.confidence * 100).toFixed(0)}%
          </p>
          <p className="text-white/85 mb-3">{data.summary}</p>
          <p className="text-sm text-white/75 mb-4">Bank: £{data.bank.toFixed(1)} • Squad value: £{data.squad_value.toFixed(1)}</p>

          <h3 className="font-semibold text-[#00ff87] mb-2">Starting XI</h3>
          <ul className="space-y-2 mb-5">
            {data.starting_xi.map((p) => (
              <li key={p.id} className="pb-2 border-b border-white/10 last:border-b-0">
                <div className="font-medium">{p.name} ({p.position}) — £{p.price.toFixed(1)} — {p.expected_points} xP</div>
                <div className="text-sm text-white/70">{p.reason}</div>
              </li>
            ))}
          </ul>

          <h3 className="font-semibold text-pink-200 mb-2">Bench</h3>
          <ul className="space-y-2 mb-5">
            {data.bench.map((p) => (
              <li key={p.id} className="pb-2 border-b border-white/10 last:border-b-0">
                <div className="font-medium">{p.name} ({p.position}) — {p.expected_points} xP</div>
              </li>
            ))}
          </ul>

          <div className="rounded-md p-3 border border-white/15 bg-black/20">
            <p><strong>Captain:</strong> {data.captain}</p>
            <p><strong>Vice:</strong> {data.vice_captain}</p>
            <p className="mt-2"><strong>Transfer:</strong> {data.transfer_out} → {data.transfer_in}</p>
            <p className="text-sm text-white/75 mt-1">{data.transfer_reason}</p>
          </div>
        </section>
      ) : null}
    </main>
  );
}
