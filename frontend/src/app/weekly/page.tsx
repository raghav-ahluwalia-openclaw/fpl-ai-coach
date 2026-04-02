"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { fetchJson } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui-state";

type Mode = "safe" | "balanced" | "aggressive";
type XpView = "1gw" | "3gw";

type AppSettings = {
  fpl_entry_id: number | null;
  entry_name?: string | null;
  player_name?: string | null;
  rival_entry_id: number | null;
};

type GameweekStatus = {
  generated_at: string;
  source: string;
  current_gw: number | null;
  current_gw_status: "in_progress" | "finished" | "unknown" | string;
  current_gw_finished: boolean | null;
  current_gw_data_checked: boolean | null;
  gw_in_progress: boolean;
  next_gw: number | null;
  next_deadline_utc: string | null;
  transfer_deadline_utc: string | null;
  seconds_until_deadline: number | null;
  transfer_window_open: boolean | null;
  season_phase: string;
};

type FixtureWindow = { counts: number[]; blanks: number; doubles: number; singles: number; label: string };

type HealthRow = {
  name: string;
  position: string;
  projected_points_1: number;
  projected_points_3: number;
  fixture_badge: "DGW" | "SGW" | "BLANK";
  injury_news: string;
  upside_safety_score: number;
  price_change_direction?: "up" | "down" | "flat" | string;
  price_change_eta_hours?: number;
  price_change_eta?: string;
  action?: "sell" | "watch" | "hold" | string;
};

type TransferMove = {
  out: string;
  in: string;
  position?: string;
  gain: number;
  projected_points_1_in?: number;
  projected_points_1_out?: number;
  projected_points_3_in: number;
  projected_points_3_out: number;
  fixture_window_next_3_in: FixtureWindow;
};

type TransferPlan = {
  plan: string;
  transfer_count: number;
  projected_gain: number;
  projected_gain_1?: number;
  projected_gain_3?: number;
  projected_gain_5?: number;
  net_gain: number;
  net_gain_1?: number;
  net_gain_3?: number;
  net_gain_5?: number;
  hit: number;
  ev?: number;
  risk_score?: number;
  confidence?: number;
  confidence_bucket?: "high" | "medium" | "low";
  note?: string;
  transfers: TransferMove[];
};

type CaptainCandidate = {
  name: string;
  safe_score: number;
  differential_score: number;
  projected_points_3: number;
  ownership_pct: number;
  fixture_window_next_3: FixtureWindow;
};

type PerformanceWeekly = {
  generated_at: string;
  captain_hit_rate: number | null;
  transfer_positive_rate: number | null;
  dashboard_card?: {
    captain_hit_rate: number | null;
    transfer_positive_rate: number | null;
    missed_captain_points: number;
    transfer_roi: number | null;
    hit_efficiency: number | null;
    benching_loss: number;
    bench_order_accuracy: number | null;
    xi_optimization_gap: number;
    avg_points_last_n: number;
    weeks_evaluated: number;
    lookback: number;
    headline: string;
  };
  confidence_calibration?: {
    status: string;
    buckets: Array<{ bucket: string; count: number; success_rate: number | null }>;
  };
};

type GameweekHub = {
  entry_id: number;
  gameweek: number;
  generated_at?: string;
  picks_source_gw?: number;
  mode: Mode;
  team_overview: {
    entry_id: number;
    gameweek: number;
    formation: string;
    strategy_mode: Mode;
    confidence: number;
    bank: number;
    squad_value: number;
  };
  fixture_context: {
    gameweek: number;
    considered: boolean;
    method: string;
    squad_window: { blank_flags_next_3: number; double_flags_next_3: number };
  };
  lineup_optimizer: {
    formation: string;
    starting_xi: Array<{ name: string; position: string; xP_next_1: number; xP_next_3: number; fixture_badge: "DGW" | "SGW" | "BLANK"; fixture_window_next_3: FixtureWindow }>;
    bench_order: Array<{ name: string; position: string; bench_rank: number; xP_next_1: number; xP_next_3: number; fixture_badge: "DGW" | "SGW" | "BLANK"; fixture_window_next_3: FixtureWindow }>;
    expected_gain_vs_current_xi_1?: number;
    expected_gain_vs_current_xi_3?: number;
    bench_order_gain_1?: number;
    bench_order_gain_3?: number;
  };
  team_health: {
    sell: HealthRow[];
    watch: HealthRow[];
    hold: HealthRow[];
    all?: HealthRow[];
  };
  top_transfer_plans: {
    one_ft: TransferPlan[];
    two_ft: TransferPlan[];
  };
  captain_matrix: {
    safe: CaptainCandidate[];
    differential: CaptainCandidate[];
  };
  explainability_v2?: {
    has_previous_snapshot: boolean;
    generated_at: string;
    decision_diff: {
      captain_changed: boolean;
      transfer_changed: boolean;
      previous: { captain: string | null; vice_captain: string | null; transfer_out: string | null; transfer_in: string | null };
      current: { captain: string | null; vice_captain: string | null; transfer_out: string | null; transfer_in: string | null };
    };
    confidence_drift: { previous: number | null; current: number; delta: number | null; direction: "up" | "down" | "flat" | "unknown" };
    factor_deltas: Array<{ key: string; label: string; previous: number; current: number; delta: number; direction: "up" | "down" }>;
    summary_reason: string;
  };
  what_changed: Array<Record<string, unknown>>;
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

const sectionTabs = [
  { id: "summary", label: "Summary" },
  { id: "changes", label: "Changes" },
  { id: "overview", label: "Overview" },
  { id: "performance", label: "Performance" },
  { id: "lineup", label: "Lineup" },
  { id: "transfers", label: "Transfers" },
  { id: "captaincy", label: "Captaincy" },
  { id: "health", label: "Health" },
] as const;

function badgeClass(badge?: "DGW" | "SGW" | "BLANK") {
  if (badge === "DGW") return "border-emerald-300 text-emerald-200";
  if (badge === "BLANK") return "border-rose-300 text-rose-200";
  return "border-white/30 text-white/80";
}

function xpVal(xpView: XpView, xp1: number, xp3: number): number {
  return xpView === "3gw" ? xp3 : xp1;
}

function planConfidenceClass(confidence?: number): string {
  const pct = Math.round((confidence ?? 0) * 100);
  if (pct > 90) return "text-emerald-300"; // high confidence
  if (pct >= 40) return "text-amber-300"; // medium confidence
  return "text-orange-300"; // low confidence
}

function priceEtaClass(direction?: string): string {
  if (direction === "up") return "text-emerald-300";
  if (direction === "down") return "text-rose-300";
  return "text-white/75";
}

function priceEtaLabel(direction?: string, eta?: string): string {
  if (direction === "up") return `▲ ${eta ?? "—"}`;
  if (direction === "down") return `▼ ${eta ?? "—"}`;
  return `▷ ${eta ?? "—"}`;
}

type KpiTone = "good" | "watch" | "bad";

function kpiToneClass(tone: KpiTone): string {
  if (tone === "good") return "text-emerald-300";
  if (tone === "bad") return "text-rose-300";
  return "text-amber-300";
}

function kpiToneLabel(tone: KpiTone): string {
  if (tone === "good") return "Good";
  if (tone === "bad") return "Bad";
  return "Watch";
}

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

function formatCountdown(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  const abs = Math.abs(seconds);
  const days = Math.floor(abs / 86400);
  const hours = Math.floor((abs % 86400) / 3600);
  const minutes = Math.floor((abs % 3600) / 60);
  const label = `${days}d ${hours}h ${minutes}m`;
  return seconds >= 0 ? label : `-${label}`;
}

function evaluateKpi(
  key: "captain_hit_rate" | "transfer_positive_rate" | "missed_captain_points" | "transfer_roi" | "hit_efficiency" | "benching_loss" | "bench_order_accuracy" | "xi_optimization_gap",
  value: number | null,
  weeks: number,
): KpiTone {
  if (value === null || !Number.isFinite(value)) return "watch";

  const perGw = weeks > 0 ? value / weeks : value;
  switch (key) {
    case "captain_hit_rate":
      return value >= 0.4 ? "good" : value < 0.25 ? "bad" : "watch";
    case "transfer_positive_rate":
      return value >= 0.55 ? "good" : value < 0.4 ? "bad" : "watch";
    case "missed_captain_points":
      return perGw <= 2 ? "good" : perGw > 4 ? "bad" : "watch";
    case "transfer_roi":
      return value >= 0.2 ? "good" : value < 0 ? "bad" : "watch";
    case "hit_efficiency":
      return value >= 1.0 ? "good" : value < 0.6 ? "bad" : "watch";
    case "benching_loss":
      return perGw <= 2 ? "good" : perGw > 4 ? "bad" : "watch";
    case "bench_order_accuracy":
      return value >= 0.5 ? "good" : value < 0.33 ? "bad" : "watch";
    case "xi_optimization_gap":
      return perGw <= 2 ? "good" : perGw > 4 ? "bad" : "watch";
    default:
      return "watch";
  }
}

export default function WeeklyPage() {
  const [teamId, setTeamId] = useState("");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [mode, setMode] = useState<Mode>("balanced");
  const [xpView, setXpView] = useState<XpView>("1gw");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<GameweekHub | null>(null);
  const [gwStatus, setGwStatus] = useState<GameweekStatus | null>(null);
  const [performance, setPerformance] = useState<PerformanceWeekly | null>(null);
  const [performanceInfoOpen, setPerformanceInfoOpen] = useState(false);
  const [performanceInfoPinned, setPerformanceInfoPinned] = useState(false);
  const [captainInfoOpen, setCaptainInfoOpen] = useState(false);
  const [captainInfoPinned, setCaptainInfoPinned] = useState(false);
  const [lineupInfoOpen, setLineupInfoOpen] = useState(false);
  const [lineupInfoPinned, setLineupInfoPinned] = useState(false);
  const hasAutoRun = useRef(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const run = useCallback(async (
    idOverride?: string,
    options?: { forceImport?: boolean; cacheMode?: RequestCache },
  ) => {
    const id = (idOverride ?? teamId).trim();
    if (!/^\d+$/.test(id)) {
      setError("Team ID must be numeric.");
      return;
    }

    const forceImport = options?.forceImport ?? false;
    const cacheMode = options?.cacheMode ?? "default";

    if (forceImport) {
      setIsRefreshing(true);
    } else {
      setLoading(true);
    }

    setError(null);

    try {
      if (forceImport) {
        // Heavy operation; run only on explicit refresh.
        await fetchJson(`/internal/team/${id}/import`, { method: "POST", cacheMode: "no-store" });
      }

      const [hub, perf, status] = await Promise.all([
        fetchJson<GameweekHub>(`/api/fpl/team/${id}/gameweek-hub?mode=${mode}`, { cacheMode }),
        fetchJson<PerformanceWeekly>(`/api/fpl/team/${id}/performance/weekly?lookback=8`, { cacheMode }),
        fetchJson<GameweekStatus>("/api/fpl/gameweek-status", { cacheMode: "force-cache" }),
      ]);
      setData(hub);
      setPerformance(perf);
      setGwStatus(status);
      if (typeof window !== "undefined") {
        localStorage.setItem("fpl_weekly_loaded", "true");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load Gameweek Hub");
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [mode, teamId]);

  useEffect(() => {
    let canceled = false;

    (async () => {
      try {
        const [s, status] = await Promise.all([
          fetchJson<AppSettings>("/internal/settings", { cacheMode: "no-store" }),
          fetchJson<GameweekStatus>("/api/fpl/gameweek-status", { cacheMode: "force-cache" }),
        ]);
        if (canceled) return;

        setSettings(s);
        setGwStatus(status);
        if (s.fpl_entry_id) {
          const id = String(s.fpl_entry_id);
          setTeamId(id);
          if (!hasAutoRun.current) {
            hasAutoRun.current = true;
            // Fast path: avoid import on initial load.
            void run(id, { forceImport: false, cacheMode: "force-cache" });
          }
        }
      } catch {
        // silent for initial shell rendering
      }
    })();

    return () => {
      canceled = true;
    };
  }, [run]);

  const retryLoad = () => void run(undefined, { forceImport: false, cacheMode: "no-store" });

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl sm:text-2xl sm:text-3xl font-black">Gameweek Hub</h1>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <div className="inline-flex rounded-md border border-white/20 overflow-hidden">
            <button
              type="button"
              onClick={() => setXpView("1gw")}
              className={`px-3 py-2 text-sm ${xpView === "1gw" ? "bg-[#00ff87] text-[#37003c]" : "bg-black/30 text-white/80"}`}
            >
              xP 1GW
            </button>
            <button
              type="button"
              onClick={() => setXpView("3gw")}
              className={`px-3 py-2 text-sm ${xpView === "3gw" ? "bg-[#00ff87] text-[#37003c]" : "bg-black/30 text-white/80"}`}
            >
              xP 3GW
            </button>
          </div>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as Mode)}
            className="rounded-md h-10 px-3 bg-black/30 border border-white/20"
          >
            <option value="safe">Safe</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </div>
      </div>

      <nav className="mb-4 overflow-x-auto" aria-label="Gameweek sections">
        <div className="inline-flex gap-2 min-w-max rounded-xl border border-white/15 bg-black/20 p-1">
          {sectionTabs.map((tab) => (
            <a
              key={tab.id}
              href={`#${tab.id}`}
              className="px-3 py-1.5 text-xs md:text-sm rounded-md text-white/85 hover:text-[#00ff87] hover:bg-white/10"
            >
              {tab.label}
            </a>
          ))}
        </div>
      </nav>

      <section id="overview" className={`${cardClass} mb-4`}>
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <div>
            {settings?.fpl_entry_id ? (
              <div className="flex flex-col">
                <span className="text-xs text-white/70 uppercase tracking-wider font-bold">FPL Team</span>
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
                onClick={() => void run(undefined, { forceImport: true, cacheMode: "no-store" })}
                disabled={loading || isRefreshing}
                className="h-10 w-10 grid place-items-center rounded-full border border-white/30 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87] transition disabled:opacity-60"
                aria-label="Refresh team data"
                title={isRefreshing ? "Refreshing..." : "Refresh team data"}
              >
                {isRefreshing ? (
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

      {gwStatus ? (
        <section className={`${cardClass} mb-4`}>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <h2 className="font-semibold text-[#00ff87]">Gameweek Status</h2>
            <span className={`text-xs rounded-full px-2 py-0.5 border ${gwStatus.gw_in_progress ? "border-emerald-300 text-emerald-200" : "border-amber-300 text-amber-200"}`}>
              {gwStatus.gw_in_progress ? "GW in progress" : "Between gameweeks"}
            </span>
          </div>
          <div className="grid md:grid-cols-2 gap-2 text-sm text-white/85">
            <p>Current GW: <strong>{gwStatus.current_gw ?? "—"}</strong> ({gwStatus.current_gw_status.replace("_", " ")})</p>
            <p>Next GW: <strong>{gwStatus.next_gw ?? "—"}</strong></p>
            <p>Transfer deadline: <strong>{formatUtc(gwStatus.transfer_deadline_utc)}</strong></p>
            <p>Time to deadline: <strong>{formatCountdown(gwStatus.seconds_until_deadline)}</strong></p>
          </div>
          <p className="text-xs text-white/80 mt-2">Season phase: {gwStatus.season_phase.replace("_", " ")} • Source: {gwStatus.source}</p>
        </section>
      ) : null}

      {error ? (
        <div className="mb-4">
          <ErrorState message={error} onRetry={retryLoad} />
        </div>
      ) : null}

      {loading && !data && !error ? (
        <div className="mb-4">
          <LoadingState label="Loading Gameweek Hub..." />
        </div>
      ) : null}

      {!loading && !error && settings?.fpl_entry_id && !data ? (
        <div className="mb-4">
          <EmptyState
            title="No gameweek data yet"
            description="Tap retry or use refresh to pull latest squad + projections."
            onRetry={retryLoad}
          />
        </div>
      ) : null}

      {data ? (
        <div className="grid gap-4">
          {/* Weekly Action Summary Section */}
          <section id="summary" className={`${cardClass} bg-gradient-to-br from-[#00ff87]/15 to-transparent border-[#00ff87]/30 shadow-lg shadow-[#00ff87]/5`}>
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className="text-xl font-black text-[#00ff87] tracking-tight">Weekly Action Summary</h2>
              <div className="text-xs text-[#00ff87]/70 font-medium px-2 py-0.5 rounded-full border border-[#00ff87]/30 bg-[#00ff87]/5 uppercase tracking-wider">
                What to do now
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* Captaincy Summary */}
              <div className="space-y-1.5 p-3 rounded-xl border border-white/10 bg-black/20">
                <p className="text-[10px] text-white/70 uppercase font-bold tracking-widest">Captaincy</p>
                <div className="flex flex-col">
                  <span className="text-lg font-bold text-white leading-tight">
                    {(data.captain_matrix.safe[0]?.name) || "—"}
                  </span>
                  <span className="text-xs text-white/80">
                    Vice: {(data.captain_matrix.safe[1]?.name) || "—"}
                  </span>
                </div>
              </div>

              {/* Transfers Summary */}
              <div className="space-y-1.5 p-3 rounded-xl border border-white/10 bg-black/20">
                <p className="text-[10px] text-white/70 uppercase font-bold tracking-widest">Plan A (Transfer)</p>
                <div className="flex flex-col">
                  <span className="text-lg font-bold text-white leading-tight truncate">
                    {(data.top_transfer_plans.one_ft[0]?.plan) || (data.top_transfer_plans.two_ft[0]?.plan) || "No Transfers Recommended"}
                  </span>
                  <span className="text-xs text-white/80">
                    Net Gain: {((data.top_transfer_plans.one_ft[0]?.net_gain_1) || (data.top_transfer_plans.two_ft[0]?.net_gain_1) || 0).toFixed(2)} xP
                  </span>
                </div>
              </div>

              {/* Lineup Summary */}
              <div className="space-y-1.5 p-3 rounded-xl border border-white/10 bg-black/20">
                <p className="text-[10px] text-white/70 uppercase font-bold tracking-widest">Lineup Optimization</p>
                <div className="flex flex-col">
                  <span className="text-lg font-bold text-[#00ff87] leading-tight">
                    +{(data.lineup_optimizer.expected_gain_vs_current_xi_1 || 0).toFixed(2)} xP
                  </span>
                  <span className="text-xs text-white/80">
                    Formation: {data.lineup_optimizer.formation}
                  </span>
                </div>
              </div>

              {/* Confidence Summary */}
              <div className="space-y-1.5 p-3 rounded-xl border border-white/10 bg-black/20">
                <p className="text-[10px] text-white/70 uppercase font-bold tracking-widest">Strategy Pulse</p>
                <div className="flex items-center gap-3">
                  <div className="flex flex-col">
                    <span className={`text-lg font-bold leading-tight ${planConfidenceClass(data.team_overview.confidence)}`}>
                      {Math.round(data.team_overview.confidence * 100)}%
                    </span>
                    <span className="text-xs text-white/80">Confidence</span>
                  </div>
                  <div className="h-8 w-px bg-white/10" />
                  <div className="flex flex-col">
                    <span className="text-lg font-bold text-white leading-tight">
                      {(data.top_transfer_plans.one_ft[0]?.risk_score || data.top_transfer_plans.two_ft[0]?.risk_score || 0).toFixed(1)}
                    </span>
                    <span className="text-xs text-white/80">Risk Score</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section id="changes" className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">What changed since last run</h2>
            {data.explainability_v2?.has_previous_snapshot ? (
              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                  <div className="rounded-md border border-white/10 bg-black/20 p-2.5">
                    <p className="text-white/75">Captain</p>
                    <p className="text-white/90">
                      {data.explainability_v2.decision_diff.previous.captain || "—"} → {data.explainability_v2.decision_diff.current.captain || "—"}
                    </p>
                  </div>
                  <div className="rounded-md border border-white/10 bg-black/20 p-2.5">
                    <p className="text-white/75">Transfer</p>
                    <p className="text-white/90">
                      {(data.explainability_v2.decision_diff.previous.transfer_out || "—")}→{(data.explainability_v2.decision_diff.previous.transfer_in || "—")}
                      {"  "}to{"  "}
                      {(data.explainability_v2.decision_diff.current.transfer_out || "—")}→{(data.explainability_v2.decision_diff.current.transfer_in || "—")}
                    </p>
                  </div>
                  <div className="rounded-md border border-white/10 bg-black/20 p-2.5">
                    <p className="text-white/75">Confidence drift</p>
                    <p className={`font-semibold ${data.explainability_v2.confidence_drift.direction === "up" ? "text-emerald-300" : data.explainability_v2.confidence_drift.direction === "down" ? "text-rose-300" : "text-amber-300"}`}>
                      {data.explainability_v2.confidence_drift.previous !== null
                        ? `${Math.round((data.explainability_v2.confidence_drift.previous || 0) * 100)}% → ${Math.round((data.explainability_v2.confidence_drift.current || 0) * 100)}%`
                        : `${Math.round((data.explainability_v2.confidence_drift.current || 0) * 100)}%`}
                    </p>
                  </div>
                </div>

                {data.explainability_v2.factor_deltas?.length ? (
                  <div className="flex flex-wrap gap-2">
                    {data.explainability_v2.factor_deltas.map((f) => (
                      <span
                        key={f.key}
                        className={`text-xs rounded-full px-2 py-1 border ${f.delta >= 0 ? "border-emerald-300/40 text-emerald-200" : "border-rose-300/40 text-rose-200"}`}
                      >
                        {f.label} {f.delta >= 0 ? "+" : ""}{f.delta.toFixed(2)}
                      </span>
                    ))}
                  </div>
                ) : null}

                <p className="text-white/85">{data.explainability_v2.summary_reason}</p>
              </div>
            ) : (
              <p className="text-sm text-white/80">First tracked run for this gameweek/mode. We’ll show decision diffs after your next refresh.</p>
            )}
          </section>

          {performance?.dashboard_card ? (() => {
            const perfCard = performance.dashboard_card;
            return (
              <section id="performance" className={cardClass}>
                <div className="flex items-center gap-2 mb-2">
                  <h2 className="font-semibold text-[#00ff87]">Performance Snapshot</h2>
                  <button
                    type="button"
                    aria-label="Performance KPI info"
                    title="How performance KPIs are calculated"
                    className="h-5 w-5 rounded-full border border-white/35 text-[11px] text-white/85 hover:border-[#00ff87] hover:text-[#00ff87] transition"
                    onMouseEnter={() => {
                      if (!performanceInfoPinned) setPerformanceInfoOpen(true);
                    }}
                    onMouseLeave={() => {
                      if (!performanceInfoPinned) setPerformanceInfoOpen(false);
                    }}
                    onClick={() => {
                      if (performanceInfoPinned) {
                        setPerformanceInfoPinned(false);
                        setPerformanceInfoOpen(false);
                      } else {
                        setPerformanceInfoPinned(true);
                        setPerformanceInfoOpen(true);
                      }
                    }}
                  >
                    i
                  </button>
                </div>
                <p className="text-sm text-white/90 mb-3">Weeks evaluated: {perfCard.weeks_evaluated} (last {perfCard.lookback} GWs)</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs md:text-sm">
                  {([
                    {
                      label: "Captain Hit Rate",
                      key: "captain_hit_rate",
                      value: perfCard.captain_hit_rate,
                      display: `${Math.round((perfCard.captain_hit_rate ?? 0) * 100)}%`,
                    },
                    {
                      label: "Transfer Positive Rate",
                      key: "transfer_positive_rate",
                      value: perfCard.transfer_positive_rate,
                      display: `${Math.round((perfCard.transfer_positive_rate ?? 0) * 100)}%`,
                    },
                    {
                      label: "Missed Captain Points",
                      key: "missed_captain_points",
                      value: perfCard.missed_captain_points,
                      display: perfCard.missed_captain_points.toFixed(1),
                    },
                    {
                      label: "Transfer ROI",
                      key: "transfer_roi",
                      value: perfCard.transfer_roi,
                      display: perfCard.transfer_roi !== null ? perfCard.transfer_roi.toFixed(2) : "—",
                    },
                    {
                      label: "Hit Efficiency",
                      key: "hit_efficiency",
                      value: perfCard.hit_efficiency,
                      display: perfCard.hit_efficiency !== null ? perfCard.hit_efficiency.toFixed(2) : "—",
                    },
                    {
                      label: "Benching Loss",
                      key: "benching_loss",
                      value: perfCard.benching_loss,
                      display: perfCard.benching_loss.toFixed(1),
                    },
                    {
                      label: "Bench Order Accuracy",
                      key: "bench_order_accuracy",
                      value: perfCard.bench_order_accuracy,
                      display: perfCard.bench_order_accuracy !== null ? `${Math.round(perfCard.bench_order_accuracy * 100)}%` : "—",
                    },
                    {
                      label: "XI Optimization Gap",
                      key: "xi_optimization_gap",
                      value: perfCard.xi_optimization_gap,
                      display: perfCard.xi_optimization_gap.toFixed(1),
                    },
                  ] as const).map((kpi) => {
                    const tone = evaluateKpi(kpi.key, kpi.value, perfCard.weeks_evaluated);
                    return (
                      <div key={kpi.label} className="rounded-md border border-white/10 bg-black/20 p-2.5">
                        <p className="text-white/75">{kpi.label}</p>
                        <p className="font-semibold">{kpi.display}</p>
                        <p className={`text-[11px] mt-0.5 ${kpiToneClass(tone)}`}>{kpiToneLabel(tone)}</p>
                      </div>
                    );
                  })}
                </div>
              </section>
            );
          })() : null}


          <section id="lineup" className={cardClass}>
            <div className="flex items-center gap-2 mb-2">
              <h2 className="font-semibold text-[#00ff87]">Lineup Optimizer • {data.lineup_optimizer.formation}</h2>
              <button
                type="button"
                aria-label="Lineup optimizer info"
                title="How lineup gain metrics are calculated"
                className="h-5 w-5 rounded-full border border-white/35 text-[11px] text-white/85 hover:border-[#00ff87] hover:text-[#00ff87] transition"
                onMouseEnter={() => {
                  if (!lineupInfoPinned) setLineupInfoOpen(true);
                }}
                onMouseLeave={() => {
                  if (!lineupInfoPinned) setLineupInfoOpen(false);
                }}
                onClick={() => {
                  if (lineupInfoPinned) {
                    setLineupInfoPinned(false);
                    setLineupInfoOpen(false);
                  } else {
                    setLineupInfoPinned(true);
                    setLineupInfoOpen(true);
                  }
                }}
              >
                i
              </button>
            </div>
            <p className="text-xs text-white/85 mb-2">
              Gain vs current XI: {xpView === "1gw"
                ? (data.lineup_optimizer.expected_gain_vs_current_xi_1 ?? 0).toFixed(2)
                : (data.lineup_optimizer.expected_gain_vs_current_xi_3 ?? 0).toFixed(2)} xP
              {" • "}
              Bench order edge: {xpView === "1gw"
                ? (data.lineup_optimizer.bench_order_gain_1 ?? 0).toFixed(2)
                : (data.lineup_optimizer.bench_order_gain_3 ?? 0).toFixed(2)} weighted xP
            </p>
            <div className="overflow-x-auto focus-visible:outline-none" tabIndex={0} role="region" aria-label="Lineup table">
              <table className="w-full text-xs md:text-sm">
                <thead>
                  <tr className="text-left text-white/85 border-b border-white/10">
                    <th className="py-2 whitespace-nowrap">Player</th>
                    <th className="py-2 whitespace-nowrap">Pos</th>
                    <th className="py-2 whitespace-nowrap">{xpView === "1gw" ? "xP (1GW)" : "xP (3GW)"}</th>
                    <th className="py-2 whitespace-nowrap">GW</th>
                    <th className="py-2 whitespace-nowrap">Role</th>
                  </tr>
                </thead>
                <tbody>
                  {data.lineup_optimizer.starting_xi.map((p) => (
                    <tr key={`xi-${p.name}`} className="border-b border-white/5">
                      <td className="py-2 font-medium">{p.name}</td>
                      <td className="py-2">{p.position}</td>
                      <td className="py-2">{xpVal(xpView, p.xP_next_1, p.xP_next_3).toFixed(2)}</td>
                      <td className="py-2"><span className={`text-xs rounded-full px-2 py-0.5 border ${badgeClass(p.fixture_badge)}`}>{p.fixture_badge}</span></td>
                      <td className="py-2 text-[#00ff87] whitespace-nowrap">XI</td>
                    </tr>
                  ))}
                  {data.lineup_optimizer.bench_order.map((p) => (
                    <tr key={`bench-${p.name}`} className="border-b border-white/5">
                      <td className="py-2 font-medium">{p.name}</td>
                      <td className="py-2">{p.position}</td>
                      <td className="py-2">{xpVal(xpView, p.xP_next_1, p.xP_next_3).toFixed(2)}</td>
                      <td className="py-2"><span className={`text-xs rounded-full px-2 py-0.5 border ${badgeClass(p.fixture_badge)}`}>{p.fixture_badge}</span></td>
                      <td className="py-2 text-pink-200 whitespace-nowrap">Bench {p.bench_rank}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section id="health" className={cardClass}>
            <div className="flex items-baseline justify-between gap-3 mb-1">
              <h2 className="font-semibold text-[#00ff87]">Team Health</h2>
              <span className="text-xs text-white/80">Bank £{data.team_overview.bank.toFixed(1)} • Value £{data.team_overview.squad_value.toFixed(1)}</span>
            </div>
            <p className="text-xs text-white/80 mb-2">Showing {(data.team_health.all ?? [...data.team_health.sell, ...data.team_health.watch, ...data.team_health.hold]).length} players from your squad.</p>
            <div className="overflow-x-auto focus-visible:outline-none" tabIndex={0} role="region" aria-label="Team health table">
              <table className="w-full text-xs md:text-sm">
                <thead>
                  <tr className="text-left text-white/85 border-b border-white/10">
                    <th className="py-2 whitespace-nowrap">Player</th>
                    <th className="py-2 whitespace-nowrap">Pos</th>
                    <th className="py-2 whitespace-nowrap">GW</th>
                    <th className="py-2 whitespace-nowrap">Action</th>
                    <th className="py-2 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1">
                        Price Delta
                        <span
                          className="text-[11px] text-white/80 border border-white/30 rounded-full h-4 w-4 inline-flex items-center justify-center"
                          title="Price Delta shows estimated direction and time to next price move: ▲ up, ▼ down, ▷ flat. ETA is a heuristic from ownership/form, points profile, and availability risk."
                        >
                          i
                        </span>
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(data.team_health.all ?? [...data.team_health.sell, ...data.team_health.watch, ...data.team_health.hold]).map((p) => {
                    const action = p.action ?? (data.team_health.sell.includes(p) ? "sell" : data.team_health.watch.includes(p) ? "watch" : "hold");
                    return (
                      <tr key={`h-${p.name}`} className="border-b border-white/5">
                        <td className="py-2 font-medium">{p.name}</td>
                        <td className="py-2">{p.position}</td>
                        <td className="py-2"><span className={`text-xs rounded-full px-2 py-0.5 border ${badgeClass(p.fixture_badge)}`}>{p.fixture_badge}</span></td>
                        <td className="py-2">
                          <span className={`text-xs rounded-full px-2 py-0.5 border ${action === "sell" ? "border-rose-300 text-rose-200" : action === "watch" ? "border-amber-300 text-amber-200" : "border-emerald-300 text-emerald-200"}`}>
                            {action.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-2">
                          <span className={`text-xs rounded-full px-2 py-0.5 border ${p.price_change_direction === "up" ? "border-emerald-300/60" : p.price_change_direction === "down" ? "border-rose-300/60" : "border-white/25"} ${priceEtaClass(p.price_change_direction)}`}>
                            {priceEtaLabel(p.price_change_direction, p.price_change_eta)}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section id="transfers" className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Top Transfer Plans (A/B/C)</h2>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <div>
                <h3 className="font-semibold mb-2 text-white">1FT</h3>
                {data.top_transfer_plans.one_ft.map((p) => (
                  <div key={`1ft-${p.plan}`} className="rounded-lg border border-white/10 p-3 bg-black/20 mb-2">
                    <p className="font-medium text-white">{p.plan} • Expected Net Gain {xpView === "1gw" ? (p.net_gain_1 ?? p.net_gain) : (p.net_gain_3 ?? p.net_gain)} • Hit {p.hit}</p>
                    <p className="text-xs text-white/80">Risk {(p.risk_score ?? 0).toFixed(2)} • <span className={planConfidenceClass(p.confidence)}>Confidence {Math.round((p.confidence ?? 0) * 100)}%</span></p>
                    {p.note ? <p className="text-xs text-white/75 mt-1">{p.note}</p> : null}
                    {p.transfers.map((t, i) => (
                      <p key={`${p.plan}-1-${i}`} className="text-white/90">
                        [{t.position || "POS"}] {t.out} ({xpView === "1gw" ? "xP1" : "xP3"} {xpView === "1gw" ? (t.projected_points_1_out ?? t.projected_points_3_out) : t.projected_points_3_out}) → {t.in} ({xpView === "1gw" ? "xP1" : "xP3"} {xpView === "1gw" ? (t.projected_points_1_in ?? t.projected_points_3_in) : t.projected_points_3_in})
                      </p>
                    ))}
                  </div>
                ))}
              </div>
              <div>
                <h3 className="font-semibold mb-2 text-white">2FT</h3>
                {data.top_transfer_plans.two_ft.map((p) => (
                  <div key={`2ft-${p.plan}`} className="rounded-lg border border-white/10 p-3 bg-black/20 mb-2">
                    <p className="font-medium text-white">{p.plan} • Expected Net Gain {xpView === "1gw" ? (p.net_gain_1 ?? p.net_gain) : (p.net_gain_3 ?? p.net_gain)} • Hit {p.hit}</p>
                    <p className="text-xs text-white/80">Risk {(p.risk_score ?? 0).toFixed(2)} • <span className={planConfidenceClass(p.confidence)}>Confidence {Math.round((p.confidence ?? 0) * 100)}%</span></p>
                    {p.note ? <p className="text-xs text-white/75 mt-1">{p.note}</p> : null}
                    {p.transfers.map((t, i) => (
                      <p key={`${p.plan}-2-${i}`} className="text-white/90">
                        [{t.position || "POS"}] {t.out} ({xpView === "1gw" ? "xP1" : "xP3"} {xpView === "1gw" ? (t.projected_points_1_out ?? t.projected_points_3_out) : t.projected_points_3_out}) → {t.in} ({xpView === "1gw" ? "xP1" : "xP3"} {xpView === "1gw" ? (t.projected_points_1_in ?? t.projected_points_3_in) : t.projected_points_3_in})
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </section>


          <section id="captaincy" className={cardClass}>
            <div className="flex items-center gap-2 mb-2">
              <h2 className="font-semibold text-[#00ff87]">Captain Matrix</h2>
              <button
                type="button"
                aria-label="Captain score info"
                title="How captain scores are calculated"
                className="h-5 w-5 rounded-full border border-white/35 text-[11px] text-white/85 hover:border-[#00ff87] hover:text-[#00ff87] transition"
                onMouseEnter={() => {
                  if (!captainInfoPinned) setCaptainInfoOpen(true);
                }}
                onMouseLeave={() => {
                  if (!captainInfoPinned) setCaptainInfoOpen(false);
                }}
                onClick={() => {
                  if (captainInfoPinned) {
                    setCaptainInfoPinned(false);
                    setCaptainInfoOpen(false);
                  } else {
                    setCaptainInfoPinned(true);
                    setCaptainInfoOpen(true);
                  }
                }}
              >
                i
              </button>
            </div>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <div>
                <h3 className="font-semibold mb-2">Safe</h3>
                {data.captain_matrix.safe.map((c) => (
                  <p key={`safe-${c.name}`}>{c.name} • score {c.safe_score}</p>
                ))}
              </div>
              <div>
                <h3 className="font-semibold mb-2">Differential</h3>
                {data.captain_matrix.differential.map((c) => (
                  <p key={`diff-${c.name}`}>{c.name} • score {c.differential_score} • own {c.ownership_pct}%</p>
                ))}
              </div>
            </div>
          </section>
        </div>
      ) : null}

      {performanceInfoOpen ? (
        <div
          className="fixed inset-0 z-50 bg-black/55 backdrop-blur-[1px] flex items-center justify-center p-4"
          onClick={() => {
            setPerformanceInfoOpen(false);
            setPerformanceInfoPinned(false);
          }}
        >
          <div
            className="max-w-xl w-full rounded-2xl border border-white/20 bg-[#1a1020] p-5 text-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <button
                type="button"
                className="text-white/70 hover:text-white"
                onClick={() => {
                  setPerformanceInfoOpen(false);
                  setPerformanceInfoPinned(false);
                }}
                aria-label="Close performance KPI info"
              >
                ✕
              </button>
            </div>
            <div className="space-y-2 text-white/85 leading-relaxed">
              <p><strong>Captain Hit Rate</strong>: % of evaluated gameweeks where your captain matched or beat the highest-scoring starter in your XI.</p>
              <p><strong>Transfer Positive Rate</strong>: % of weeks with transfers where net transfer gain (after hit cost) was positive.</p>
              <p><strong>Missed Captain Points</strong>: total points lost versus the best starter captain choice each GW.</p>
              <p><strong>Transfer ROI</strong>: net transfer gain divided by number of transfers made.</p>
              <p><strong>Hit Efficiency</strong>: raw transfer gain per point spent on transfer hits.</p>
              <p><strong>Benching Loss</strong>: points left on the bench that could have improved XI output.</p>
              <p><strong>Bench Order Accuracy</strong>: how often your bench 1/2/3 ordering matched realized points order.</p>
              <p><strong>XI Optimization Gap</strong>: points gap between your XI and best XI from your 15-man squad.</p>
            </div>
          </div>
        </div>
      ) : null}

      {lineupInfoOpen ? (
        <div
          className="fixed inset-0 z-50 bg-black/55 backdrop-blur-[1px] flex items-center justify-center p-4"
          onClick={() => {
            setLineupInfoOpen(false);
            setLineupInfoPinned(false);
          }}
        >
          <div
            className="max-w-xl w-full rounded-2xl border border-white/20 bg-[#1a1020] p-5 text-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <button
                type="button"
                className="text-white/70 hover:text-white"
                onClick={() => {
                  setLineupInfoOpen(false);
                  setLineupInfoPinned(false);
                }}
                aria-label="Close lineup optimizer info"
              >
                ✕
              </button>
            </div>
            <div className="space-y-2 text-white/85 leading-relaxed">
              <p><strong>Gain vs current XI</strong> is the projected points difference between the recommended starting XI and your current selected XI from FPL picks.</p>
              <p><strong>Bench order edge</strong> is the weighted points difference between recommended bench order and your current bench order (bench slot 1 is weighted most because autosub impact is highest).</p>
              <p className="text-white/70">Positive values mean the optimizer setup is expected to outperform your current setup.</p>
            </div>
          </div>
        </div>
      ) : null}

      {captainInfoOpen ? (
        <div
          className="fixed inset-0 z-50 bg-black/55 backdrop-blur-[1px] flex items-center justify-center p-4"
          onClick={() => {
            setCaptainInfoOpen(false);
            setCaptainInfoPinned(false);
          }}
        >
          <div
            className="max-w-xl w-full rounded-2xl border border-white/20 bg-[#1a1020] p-5 text-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <button
                type="button"
                className="text-white/70 hover:text-white"
                onClick={() => {
                  setCaptainInfoOpen(false);
                  setCaptainInfoPinned(false);
                }}
                aria-label="Close captain score info"
              >
                ✕
              </button>
            </div>
            <div className="space-y-2 text-white/85 leading-relaxed">
              <p><strong>Safe score</strong> ranks stable captain picks. It blends projected 3-GW output, risk penalties (minutes + availability), ownership stability, and fixture context.</p>
              <p><strong>Differential score</strong> ranks upside picks. It uses projected output with lighter risk penalty, plus extra weight for lower ownership and fixture swing opportunity.</p>
              <p className="text-white/70">These are ranking scores (higher is better within each column), not direct expected-points values.</p>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
