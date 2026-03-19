"use client";

import { useEffect, useRef, useState } from "react";

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
  chip_usage?: Record<
    "wildcard" | "free_hit" | "bench_boost" | "triple_captain",
    { used_count: number; max_uses: number; remaining: number; available: boolean; used_gws: number[] }
  >;
  chip_history?: Array<{ chip: string; label: string; gameweek?: number | null; time?: string | null }>;
  fixture_windows: { gameweek: number; blank_teams: number; double_teams: number }[];
  recommendation: string;
  alternative?: string;
  confidence?: number;
};

type AppSettings = {
  fpl_entry_id: number | null;
  rival_entry_id: number | null;
};

type RivalIntelResponse = {
  gameweek: number;
  entry_overall_rank?: number | null;
  rival_overall_rank?: number | null;
  overlap_count: number;
  my_only_count: number;
  rival_only_count: number;
  overlap_players: string[];
  my_differentials: string[];
  rival_differentials: string[];
  captaincy: {
    my_captain: string | null;
    rival_captain: string | null;
    overlap: boolean;
    risk: string;
  };
  differential_impact: {
    my_top: { name: string; xP_3: number; impact_score: number; ownership_pct: number }[];
    rival_top: { name: string; xP_3: number; impact_score: number; ownership_pct: number }[];
  };
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

export default function PlannerPage() {
  const [chip, setChip] = useState<ChipPlannerResponse | null>(null);
  const [rival, setRival] = useState<RivalIntelResponse | null>(null);
  const [entryId, setEntryId] = useState("");
  const [rivalEntryId, setRivalEntryId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const autoCompareDone = useRef(false);

  useEffect(() => {
    fetchJson<AppSettings>(`${API_BASE}/api/fpl/settings`)
      .then((s) => {
        if (s.fpl_entry_id) setEntryId((prev) => prev || String(s.fpl_entry_id));
        if (s.rival_entry_id) setRivalEntryId((prev) => prev || String(s.rival_entry_id));
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    const qs = new URLSearchParams({ horizon: "6" });
    if (entryId) qs.set("entry_id", entryId);

    fetchJson<ChipPlannerResponse>(`${API_BASE}/api/fpl/chip-planner?${qs.toString()}`)
      .then(setChip)
      .catch((e) => setError(e.message || "Failed to load chip planner"));
  }, [entryId]);

  useEffect(() => {
    if (!autoCompareDone.current && entryId && rivalEntryId) {
      autoCompareDone.current = true;
      void fetchJson<RivalIntelResponse>(
        `${API_BASE}/api/fpl/rival-intelligence?entry_id=${entryId}&rival_entry_id=${rivalEntryId}`,
      )
        .then((payload) => {
          setRival(payload);
          setError(null);
        })
        .catch((e) => setError(e.message || "Failed to load rival intelligence"));
    }
  }, [entryId, rivalEntryId]);

  async function loadRival(entryOverride?: string, rivalOverride?: string) {
    const myId = (entryOverride ?? entryId).trim();
    const rivalId = (rivalOverride ?? rivalEntryId).trim();

    if (!myId || !rivalId) {
      setError("Enter both your Team ID and Rival Team ID.");
      return;
    }
    try {
      const payload = await fetchJson<RivalIntelResponse>(
        `${API_BASE}/api/fpl/rival-intelligence?entry_id=${myId}&rival_entry_id=${rivalId}`,
      );
      setRival(payload);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load rival intelligence");
    }
  }

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-2xl sm:text-3xl font-black mb-4">Planner</h1>
      {error ? <p className="text-red-300 mb-3">{error}</p> : null}

      {chip ? (
        <section className={cardClass}>
          <h2 className="font-semibold text-[#00ff87] mb-2">Chip Planner • GW {chip.gameweek}</h2>
          <p className="text-sm text-white/75 mb-3">
            Recommendation: <strong>{chip.recommendation}</strong>
            {chip.alternative ? <> • Alt: <strong>{chip.alternative}</strong></> : null}
            {typeof chip.confidence === "number" ? <> • Confidence: <strong>{Math.round(chip.confidence * 100)}%</strong></> : null}
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-3 text-sm">
            {([
              ["wildcard", "Wildcard", chip.chip_scores.wildcard],
              ["free_hit", "Free Hit", chip.chip_scores.free_hit],
              ["bench_boost", "Bench Boost", chip.chip_scores.bench_boost],
              ["triple_captain", "Triple Captain", chip.chip_scores.triple_captain],
            ] as const).map(([key, label, score]) => {
              const usage = chip.chip_usage?.[key];
              const usedUp = usage ? usage.used_count >= 2 : false;
              return (
                <div
                  key={key}
                  className={`border border-white/10 rounded-md p-3 ${usedUp ? "bg-white/5 opacity-50" : "bg-black/20"}`}
                >
                  <p>{label}: <strong>{score.toFixed(2)}</strong></p>
                  {usage ? (
                    <p className="text-xs text-white/70 mt-1">
                      Used {usage.used_count}/{usage.max_uses}
                      {usage.used_gws?.length ? ` • GW ${usage.used_gws.join(", ")}` : ""}
                    </p>
                  ) : null}
                </div>
              );
            })}
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
        <div className="grid sm:flex gap-2 mb-3">
          <input
            value={entryId}
            onChange={(e) => setEntryId(e.target.value.replace(/\D/g, ""))}
            placeholder="Your Team ID"
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20 w-full sm:w-auto"
          />
          <input
            value={rivalEntryId}
            onChange={(e) => setRivalEntryId(e.target.value.replace(/\D/g, ""))}
            placeholder="Rival Team ID"
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20 w-full sm:w-auto"
          />
          <button onClick={() => void loadRival()} className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold w-full sm:w-auto">
            Compare
          </button>
        </div>

        {rival ? (
          <div className="text-sm text-white/85 space-y-3">
            <p>GW {rival.gameweek} • Overlap: <strong>{rival.overlap_count}</strong> • My differentials: <strong>{rival.my_only_count}</strong> • Rival differentials: <strong>{rival.rival_only_count}</strong></p>
            <p>Overall Rank — Me: <strong>{rival.entry_overall_rank ? rival.entry_overall_rank.toLocaleString() : "—"}</strong> • Rival: <strong>{rival.rival_overall_rank ? rival.rival_overall_rank.toLocaleString() : "—"}</strong></p>
            <p><strong>My differentials:</strong> {rival.my_differentials.join(", ") || "None"}</p>
            <p><strong>Rival differentials:</strong> {rival.rival_differentials.join(", ") || "None"}</p>
            <p>
              <strong>Captaincy:</strong> Me: {rival.captaincy.my_captain || "n/a"} • Rival: {rival.captaincy.rival_captain || "n/a"} •
              {" "}{rival.captaincy.overlap ? "overlap (hedged)" : "different (high swing)"}
            </p>

            <div className="grid md:grid-cols-2 gap-3">
              <div className="border border-white/10 rounded-md p-3 bg-black/20">
                <p className="font-semibold mb-1">My top impact differentials</p>
                <ul className="space-y-1">
                  {rival.differential_impact.my_top.slice(0, 5).map((p, idx) => (
                    <li key={`${p.name}-${idx}`}>{p.name} • impact {p.impact_score.toFixed(2)} • xP3 {p.xP_3.toFixed(2)}</li>
                  ))}
                </ul>
              </div>
              <div className="border border-white/10 rounded-md p-3 bg-black/20">
                <p className="font-semibold mb-1">Rival top impact differentials</p>
                <ul className="space-y-1">
                  {rival.differential_impact.rival_top.slice(0, 5).map((p, idx) => (
                    <li key={`${p.name}-${idx}`}>{p.name} • impact {p.impact_score.toFixed(2)} • xP3 {p.xP_3.toFixed(2)}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
