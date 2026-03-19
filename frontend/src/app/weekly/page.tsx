"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchJson } from "@/lib/api";

type Mode = "safe" | "balanced" | "aggressive";
type XpView = "1gw" | "3gw";

type AppSettings = { fpl_entry_id: number | null };

type FixtureWindow = { counts: number[]; blanks: number; doubles: number; singles: number; label: string };

type HealthRow = {
  name: string;
  position: string;
  projected_points_1: number;
  projected_points_3: number;
  fixture_badge: "DGW" | "SGW" | "BLANK";
  injury_news: string;
  upside_safety_score: number;
};

type TransferMove = {
  out: string;
  in: string;
  position?: string;
  gain: number;
  projected_points_3_in: number;
  projected_points_3_out: number;
  fixture_window_next_3_in: FixtureWindow;
};

type TransferPlan = {
  plan: string;
  transfer_count: number;
  projected_gain: number;
  net_gain: number;
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
  };
  top_transfer_plans: {
    one_ft: TransferPlan[];
    two_ft: TransferPlan[];
  };
  captain_matrix: {
    safe: CaptainCandidate[];
    differential: CaptainCandidate[];
  };
  what_changed: Array<Record<string, unknown>>;
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

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

export default function WeeklyPage() {
  const [teamId, setTeamId] = useState("");
  const [mode, setMode] = useState<Mode>("balanced");
  const [xpView, setXpView] = useState<XpView>("1gw");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<GameweekHub | null>(null);
  const [captainInfoOpen, setCaptainInfoOpen] = useState(false);
  const [captainInfoPinned, setCaptainInfoPinned] = useState(false);
  const [lineupInfoOpen, setLineupInfoOpen] = useState(false);
  const [lineupInfoPinned, setLineupInfoPinned] = useState(false);
  const hasAutoRun = useRef(false);

  useEffect(() => {
    fetchJson<AppSettings>("/api/fpl/settings")
      .then((s) => {
        if (s.fpl_entry_id) setTeamId((prev) => prev || String(s.fpl_entry_id));
      })
      .catch(() => null);
  }, []);

  const run = useCallback(async (idOverride?: string) => {
    const id = (idOverride ?? teamId).trim();
    if (!/^\d+$/.test(id)) {
      setError("Team ID must be numeric.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await fetchJson(`/api/fpl/team/${id}/import`, { method: "POST" });
      const hub = await fetchJson<GameweekHub>(`/api/fpl/team/${id}/gameweek-hub?mode=${mode}`);
      setData(hub);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load Gameweek Hub");
    } finally {
      setLoading(false);
    }
  }, [mode, teamId]);

  useEffect(() => {
    if (!hasAutoRun.current && /^\d+$/.test(teamId.trim())) {
      hasAutoRun.current = true;
      void run(teamId.trim());
    }
  }, [teamId, run]);

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black">Gameweek Hub</h1>
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
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
          >
            <option value="safe">Safe</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </div>
      </div>

      <section className={`${cardClass} mb-4`}>
        <div className="grid sm:flex gap-2 sm:gap-3 items-center">
          <input
            value={teamId}
            onChange={(e) => setTeamId(e.target.value.replace(/\D/g, ""))}
            placeholder="FPL Team ID"
            inputMode="numeric"
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20 w-full sm:min-w-[220px] sm:w-auto"
          />
          <button
            onClick={() => void run()}
            disabled={loading || !/^\d+$/.test(teamId.trim())}
            className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60 w-full sm:w-auto"
          >
            {loading ? "Loading..." : "Run Weekly Plan"}
          </button>
        </div>
      </section>

      {error ? <p className="text-red-300 mb-4">{error}</p> : null}

      {data ? (
        <div className="grid gap-4">
          <section className={cardClass}>
            <p className="text-sm text-white/75 mb-2">
              Entry #{data.team_overview.entry_id} • GW {data.team_overview.gameweek} • {data.team_overview.formation} • {data.team_overview.strategy_mode.toUpperCase()} • Confidence {(data.team_overview.confidence * 100).toFixed(0)}%
            </p>
            <p className="text-sm text-white/75">Bank: £{data.team_overview.bank.toFixed(1)} • Squad value: £{data.team_overview.squad_value.toFixed(1)}</p>
            {typeof data.picks_source_gw === "number" && data.picks_source_gw !== data.team_overview.gameweek ? (
              <p className="text-xs text-white/60 mt-2">Using latest available squad snapshot from GW {data.picks_source_gw}.</p>
            ) : null}
          </section>

          <section className={cardClass}>
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
            <p className="text-xs text-white/70 mb-2">
              Gain vs current XI: {xpView === "1gw"
                ? (data.lineup_optimizer.expected_gain_vs_current_xi_1 ?? 0).toFixed(2)
                : (data.lineup_optimizer.expected_gain_vs_current_xi_3 ?? 0).toFixed(2)} xP
              {" • "}
              Bench order edge: {xpView === "1gw"
                ? (data.lineup_optimizer.bench_order_gain_1 ?? 0).toFixed(2)
                : (data.lineup_optimizer.bench_order_gain_3 ?? 0).toFixed(2)} weighted xP
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs md:text-sm">
                <thead>
                  <tr className="text-left text-white/70 border-b border-white/10">
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

          <section className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Team Health</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-xs md:text-sm">
                <thead>
                  <tr className="text-left text-white/70 border-b border-white/10">
                    <th className="py-2 whitespace-nowrap">Player</th>
                    <th className="py-2 whitespace-nowrap">Pos</th>
                    <th className="py-2 whitespace-nowrap">{xpView === "1gw" ? "xP (1GW)" : "xP (3GW)"}</th>
                    <th className="py-2 whitespace-nowrap">GW</th>
                    <th className="py-2 whitespace-nowrap">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.team_health.sell, ...data.team_health.watch, ...data.team_health.hold].map((p) => {
                    const action = data.team_health.sell.includes(p) ? "sell" : data.team_health.watch.includes(p) ? "watch" : "hold";
                    return (
                      <tr key={`h-${p.name}`} className="border-b border-white/5">
                        <td className="py-2 font-medium">{p.name}</td>
                        <td className="py-2">{p.position}</td>
                        <td className="py-2">{xpVal(xpView, p.projected_points_1, p.projected_points_3).toFixed(2)}</td>
                        <td className="py-2"><span className={`text-xs rounded-full px-2 py-0.5 border ${badgeClass(p.fixture_badge)}`}>{p.fixture_badge}</span></td>
                        <td className="py-2">
                          <span className={`text-xs rounded-full px-2 py-0.5 border ${action === "sell" ? "border-rose-300 text-rose-200" : action === "watch" ? "border-amber-300 text-amber-200" : "border-emerald-300 text-emerald-200"}`}>
                            {action.toUpperCase()}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Top Transfer Plans (A/B/C)</h2>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <div>
                <h3 className="font-semibold mb-2">1FT</h3>
                {data.top_transfer_plans.one_ft.map((p) => (
                  <div key={`1ft-${p.plan}`} className="rounded-lg border border-white/10 p-3 bg-black/20 mb-2">
                    <p className="font-medium">{p.plan} • Expected Net Gain {p.ev ?? p.net_gain} • Hit {p.hit}</p>
                    <p className="text-xs text-white/70">Risk {(p.risk_score ?? 0).toFixed(2)} • <span className={planConfidenceClass(p.confidence)}>Confidence {Math.round((p.confidence ?? 0) * 100)}%</span></p>
                    {p.note ? <p className="text-xs text-white/65 mt-1">{p.note}</p> : null}
                    {p.transfers.map((t, i) => (
                      <p key={`${p.plan}-1-${i}`} className="text-white/80">
                        [{t.position || "POS"}] {t.out} (xP3 {t.projected_points_3_out}) → {t.in} (xP3 {t.projected_points_3_in})
                      </p>
                    ))}
                  </div>
                ))}
              </div>
              <div>
                <h3 className="font-semibold mb-2">2FT</h3>
                {data.top_transfer_plans.two_ft.map((p) => (
                  <div key={`2ft-${p.plan}`} className="rounded-lg border border-white/10 p-3 bg-black/20 mb-2">
                    <p className="font-medium">{p.plan} • Expected Net Gain {p.ev ?? p.net_gain} • Hit {p.hit}</p>
                    <p className="text-xs text-white/70">Risk {(p.risk_score ?? 0).toFixed(2)} • <span className={planConfidenceClass(p.confidence)}>Confidence {Math.round((p.confidence ?? 0) * 100)}%</span></p>
                    {p.note ? <p className="text-xs text-white/65 mt-1">{p.note}</p> : null}
                    {p.transfers.map((t, i) => (
                      <p key={`${p.plan}-2-${i}`} className="text-white/80">
                        [{t.position || "POS"}] {t.out} (xP3 {t.projected_points_3_out}) → {t.in} (xP3 {t.projected_points_3_in})
                      </p>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className={cardClass}>
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
              <h3 className="text-base font-semibold text-[#00ff87]">Lineup optimizer metric meaning</h3>
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
              <h3 className="text-base font-semibold text-[#00ff87]">Captain Matrix score meaning</h3>
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
