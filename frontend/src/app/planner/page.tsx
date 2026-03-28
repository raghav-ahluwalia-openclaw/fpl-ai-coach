"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { fetchJson } from "@/lib/api";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui-state";

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
  generated_at?: string;
};

type AppSettings = {
  fpl_entry_id: number | null;
  entry_name?: string | null;
  player_name?: string | null;
  rival_entry_id: number | null;
};

type GameweekStatus = {
  current_gw: number | null;
  current_gw_status: string;
  gw_in_progress: boolean;
  next_gw: number | null;
  transfer_deadline_utc: string | null;
  seconds_until_deadline: number | null;
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

function formatUtc(value?: string | null): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export default function PlannerPage() {
  const [chip, setChip] = useState<ChipPlannerResponse | null>(null);
  const [gwStatus, setGwStatus] = useState<GameweekStatus | null>(null);
  const [rival, setRival] = useState<RivalIntelResponse | null>(null);
  const [entryId, setEntryId] = useState("");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [rivalEntryId, setRivalEntryId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadingChip, setLoadingChip] = useState(false);
  const [loadingRival, setLoadingRival] = useState(false);

  useEffect(() => {
    fetchJson<AppSettings>(`${API_BASE}/api/fpl/settings`)
      .then((s) => {
        setSettings(s);
        if (s.fpl_entry_id) setEntryId(String(s.fpl_entry_id));
        if (s.rival_entry_id) setRivalEntryId(String(s.rival_entry_id));
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    fetchJson<GameweekStatus>(`${API_BASE}/api/fpl/gameweek-status`)
      .then(setGwStatus)
      .catch(() => null);
  }, []);

  const loadChip = useCallback(async (idOverride?: string) => {
    const id = (idOverride ?? entryId).trim();
    if (!id) return;
    setLoadingChip(true);
    const qs = new URLSearchParams({ horizon: "6" });
    qs.set("entry_id", id);
    try {
      const payload = await fetchJson<ChipPlannerResponse>(`${API_BASE}/api/fpl/chip-planner?${qs.toString()}`);
      setChip(payload);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load chip planner");
    } finally {
      setLoadingChip(false);
    }
  }, [entryId]);

  useEffect(() => {
    if (entryId) {
      void loadChip(entryId);
    }
  }, [entryId, loadChip]);

  const loadRival = useCallback(async (entryOverride?: string, rivalOverride?: string) => {
    const myId = (entryOverride ?? entryId).trim();
    const rivalId = (rivalOverride ?? rivalEntryId).trim();

    if (!myId || !rivalId) {
      setError("Enter both your Team ID and Rival Team ID.");
      return;
    }
    setLoadingRival(true);
    try {
      const payload = await fetchJson<RivalIntelResponse>(
        `${API_BASE}/api/fpl/rival-intelligence?entry_id=${myId}&rival_entry_id=${rivalId}`,
      );
      setRival(payload);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load rival intelligence");
    } finally {
      setLoadingRival(false);
    }
  }, [entryId, rivalEntryId]);

  useEffect(() => {
    if (entryId && rivalEntryId) {
      void loadRival(entryId, rivalEntryId);
    }
  }, [entryId, rivalEntryId, loadRival]);

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-2xl sm:text-2xl sm:text-3xl font-black mb-4">Planner</h1>

      <section className={`${cardClass} mb-4`}>
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <div>
            {settings?.fpl_entry_id ? (
              <div className="flex flex-col">
                <span className="text-xs text-white/50 uppercase tracking-wider font-bold">FPL Team</span>
                <span className="text-lg font-bold text-[#00ff87]">
                  {settings.entry_name || `Entry #${settings.fpl_entry_id}`}
                </span>
                {settings.player_name && (
                  <span className="text-sm text-white/70 italic">{settings.player_name}</span>
                )}
                {chip?.generated_at && (
                  <span className="text-[10px] text-white/40 mt-1 uppercase font-medium">
                    Updated: {new Date(chip.generated_at).toLocaleString(undefined, { timeZoneName: "short" })}
                  </span>
                )}
                {!settings.rival_entry_id && (
                  <Link 
                    href="/settings" 
                    className="mt-2 text-xs font-semibold text-amber-300/80 hover:text-amber-200 flex items-center gap-1.5 p-2 rounded-lg border border-amber-300/20 bg-amber-300/5 max-w-fit"
                  >
                    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-current">
                      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
                    </svg>
                    Setup Rival ID for competitive intelligence
                    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </Link>
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
                onClick={() => void loadChip()}
                disabled={loadingChip}
                className="h-10 w-10 grid place-items-center rounded-full border border-white/30 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87] transition disabled:opacity-60"
                aria-label="Refresh planner data"
                title={loadingChip ? "Refreshing..." : "Refresh planner data"}
              >
                {loadingChip ? (
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
          <ErrorState message={error} onRetry={() => void loadChip()} />
        </div>
      ) : null}

      {gwStatus ? (
        <section className={`${cardClass} mb-4`}>
          <h2 className="font-semibold text-[#00ff87] mb-2">Gameweek Status</h2>
          <div className="grid md:grid-cols-2 gap-2 text-sm text-white/85">
            <p>Current GW: <strong>{gwStatus.current_gw ?? "—"}</strong> ({gwStatus.current_gw_status.replace("_", " ")})</p>
            <p>Next GW: <strong>{gwStatus.next_gw ?? "—"}</strong></p>
            <p>Transfer deadline: <strong>{formatUtc(gwStatus.transfer_deadline_utc)}</strong></p>
            <p>Status: <strong>{gwStatus.gw_in_progress ? "GW in progress" : "Between gameweeks"}</strong></p>
          </div>
        </section>
      ) : null}

      {loadingChip && !chip ? (
        <div className="mb-4">
          <LoadingState label="Analyzing chip strategy..." />
        </div>
      ) : chip ? (
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
      ) : !loadingChip && !error && settings?.fpl_entry_id ? (
        <div className="mb-4">
          <EmptyState 
            title="No chip strategy data" 
            description="We couldn't generate a chip strategy at this moment."
            onRetry={() => void loadChip()}
          />
        </div>
      ) : null}

      <section className={`${cardClass} mt-4`}>
        <h2 className="font-semibold text-[#00ff87] mb-2">Rival Intelligence</h2>
        <div className="grid sm:flex gap-2 mb-3 items-end">
          <div className="flex-1">
            <label className="block text-xs text-white/50 mb-1 uppercase font-bold tracking-wider">Your Team</label>
            {settings?.fpl_entry_id ? (
              <div className="rounded-md h-10 px-3 bg-white/5 border border-white/10 flex items-center">
                <span className="text-sm font-medium truncate">{settings.entry_name || settings.fpl_entry_id}</span>
              </div>
            ) : (
              <input
                value={entryId}
                onChange={(e) => setEntryId(e.target.value.replace(/\D/g, ""))}
                placeholder="Your Team ID"
                className="rounded-md h-10 px-3 bg-black/30 border border-white/20 w-full"
              />
            )}
          </div>
          <div className="flex-1">
            <label className="block text-xs text-white/50 mb-1 uppercase font-bold tracking-wider">Rival Team ID</label>
            <input
              value={rivalEntryId}
              onChange={(e) => setRivalEntryId(e.target.value.replace(/\D/g, ""))}
              placeholder="e.g. 123456"
              className="rounded-md h-10 px-3 bg-black/30 border border-white/20 w-full"
            />
          </div>
          <button
            onClick={() => void loadRival()}
            disabled={loadingRival || !rivalEntryId}
            className="px-6 h-10 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            {loadingRival ? "Comparing..." : "Compare"}
          </button>
        </div>

        {loadingRival ? (
          <LoadingState label="Comparing team differentials..." />
        ) : rival ? (
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
