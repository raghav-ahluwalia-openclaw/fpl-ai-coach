"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type ChipPlannerResponse = {
  gameweek: number;
  horizon: number;
  chip_scores: {
    wildcard: number;
    free_hit: number;
    bench_boost: number;
    triple_captain: number;
  };
  fixture_windows: { gameweek: number; blank_teams: number; double_teams: number }[];
  recommendation: string;
  alternative?: string;
  confidence?: number;
};

type RivalIntelResponse = {
  gameweek: number;
  overlap_count: number;
  my_only_count: number;
  rival_only_count: number;
  overlap_players: string[];
  my_differentials: string[];
  rival_differentials: string[];
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

export default function PlannerPage() {
  const [chip, setChip] = useState<ChipPlannerResponse | null>(null);
  const [rival, setRival] = useState<RivalIntelResponse | null>(null);
  const [entryId, setEntryId] = useState("");
  const [rivalEntryId, setRivalEntryId] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<ChipPlannerResponse>(`${API_BASE}/api/fpl/chip-planner?horizon=6`)
      .then(setChip)
      .catch((e) => setError(e.message || "Failed to load chip planner"));
  }, []);

  async function loadRival() {
    if (!entryId || !rivalEntryId) {
      setError("Enter both your Team ID and Rival Team ID.");
      return;
    }
    try {
      const payload = await fetchJson<RivalIntelResponse>(
        `${API_BASE}/api/fpl/rival-intelligence?entry_id=${entryId}&rival_entry_id=${rivalEntryId}`,
      );
      setRival(payload);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load rival intelligence");
    }
  }

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-3xl font-black mb-4">Planner</h1>
      {error ? <p className="text-red-300 mb-3">{error}</p> : null}

      {chip ? (
        <section className={cardClass}>
          <h2 className="font-semibold text-[#00ff87] mb-2">Chip Planner • GW {chip.gameweek}</h2>
          <p className="text-sm text-white/75 mb-3">
            Recommendation: <strong>{chip.recommendation}</strong>
            {chip.alternative ? <> • Alt: <strong>{chip.alternative}</strong></> : null}
            {typeof chip.confidence === "number" ? <> • Confidence: <strong>{Math.round(chip.confidence * 100)}%</strong></> : null}
          </p>
          <div className="grid md:grid-cols-4 gap-3 text-sm">
            <div className="border border-white/10 rounded-md p-3">Wildcard: <strong>{chip.chip_scores.wildcard.toFixed(2)}</strong></div>
            <div className="border border-white/10 rounded-md p-3">Free Hit: <strong>{chip.chip_scores.free_hit.toFixed(2)}</strong></div>
            <div className="border border-white/10 rounded-md p-3">Bench Boost: <strong>{chip.chip_scores.bench_boost.toFixed(2)}</strong></div>
            <div className="border border-white/10 rounded-md p-3">Triple Captain: <strong>{chip.chip_scores.triple_captain.toFixed(2)}</strong></div>
          </div>

          <div className="mt-3 text-sm text-white/80">
            <p className="mb-1 font-semibold">Blank/Double window:</p>
            <div className="flex flex-wrap gap-2">
              {chip.fixture_windows?.slice(0, 6).map((w) => (
                <span key={w.gameweek} className="text-xs rounded-full px-3 py-1 border border-white/20 bg-black/20">
                  GW{w.gameweek}: blank {w.blank_teams}, dbl {w.double_teams}
                </span>
              ))}
            </div>
          </div>
        </section>
      ) : (
        <p className="text-white/75">Loading chip planner...</p>
      )}

      <section className={`${cardClass} mt-4`}>
        <h2 className="font-semibold text-[#00ff87] mb-2">Rival Intelligence</h2>
        <div className="flex gap-2 flex-wrap mb-3">
          <input
            value={entryId}
            onChange={(e) => setEntryId(e.target.value.replace(/\D/g, ""))}
            placeholder="Your Team ID"
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
          />
          <input
            value={rivalEntryId}
            onChange={(e) => setRivalEntryId(e.target.value.replace(/\D/g, ""))}
            placeholder="Rival Team ID"
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
          />
          <button onClick={loadRival} className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold">
            Compare
          </button>
        </div>

        {rival ? (
          <div className="text-sm text-white/85 space-y-2">
            <p>GW {rival.gameweek} • Overlap: <strong>{rival.overlap_count}</strong> • My differentials: <strong>{rival.my_only_count}</strong> • Rival differentials: <strong>{rival.rival_only_count}</strong></p>
            <p><strong>My differentials:</strong> {rival.my_differentials.join(", ") || "None"}</p>
            <p><strong>Rival differentials:</strong> {rival.rival_differentials.join(", ") || "None"}</p>
          </div>
        ) : null}
      </section>
    </main>
  );
}
