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
  minutes_risk: number;
  availability_risk: number;
  fixture_badge: "DGW" | "SGW" | "BLANK";
  fixture_window_next_3: FixtureWindow;
  injury_news: string;
  upside_safety_score: number;
};

type TransferMove = {
  out: string;
  in: string;
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

type WeeklyCockpit = {
  entry_id: number;
  gameweek: number;
  picks_source_gw?: number;
  mode: Mode;
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

export default function WeeklyPage() {
  const [teamId, setTeamId] = useState("");
  const [mode, setMode] = useState<Mode>("balanced");
  const [xpView, setXpView] = useState<XpView>("3gw");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<WeeklyCockpit | null>(null);
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
      const cockpit = await fetchJson<WeeklyCockpit>(`/api/fpl/team/${id}/weekly-cockpit?mode=${mode}`);
      setData(cockpit);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load weekly cockpit");
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
    <main className="min-h-screen p-4 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
        <h1 className="text-3xl font-black">Weekly Cockpit</h1>
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
        <div className="flex gap-3 flex-wrap items-center">
          <input
            value={teamId}
            onChange={(e) => setTeamId(e.target.value.replace(/\D/g, ""))}
            placeholder="FPL Team ID"
            inputMode="numeric"
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20 min-w-[220px]"
          />
          <button
            onClick={() => void run()}
            disabled={loading || !/^\d+$/.test(teamId.trim())}
            className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60"
          >
            {loading ? "Loading..." : "Run Weekly Plan"}
          </button>
          {data ? (
            <p className="text-sm text-white/75">
              GW {data.gameweek}
              {typeof data.picks_source_gw === "number" && data.picks_source_gw !== data.gameweek
                ? ` • using latest available squad snapshot from GW ${data.picks_source_gw}`
                : ""}
            </p>
          ) : null}
        </div>
      </section>

      {error ? <p className="text-red-300 mb-4">{error}</p> : null}

      {data ? (
        <div className="grid gap-4">
          <section className={cardClass}>
            <p className="text-sm text-white/80">{data.fixture_context.method}</p>
            <p className="text-sm text-white/70 mt-1">
              Next-3-GW squad flags: DGW windows {data.fixture_context.squad_window.double_flags_next_3} • BLANK windows {data.fixture_context.squad_window.blank_flags_next_3}
            </p>
          </section>

          <section className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Lineup Optimizer • {data.lineup_optimizer.formation}</h2>
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
                    <th className="py-2 whitespace-nowrap">Risks</th>
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
                        <td className="py-2 text-white/75">M {p.minutes_risk.toFixed(2)} / A {p.availability_risk.toFixed(2)}</td>
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
                    <p className="font-medium">{p.plan} • Net {p.net_gain} • Hit {p.hit}</p>
                    {p.transfers.map((t, i) => (
                      <p key={`${p.plan}-1-${i}`} className="text-white/80">{t.out} → {t.in}</p>
                    ))}
                  </div>
                ))}
              </div>
              <div>
                <h3 className="font-semibold mb-2">2FT</h3>
                {data.top_transfer_plans.two_ft.map((p) => (
                  <div key={`2ft-${p.plan}`} className="rounded-lg border border-white/10 p-3 bg-black/20 mb-2">
                    <p className="font-medium">{p.plan} • Net {p.net_gain} • Hit {p.hit}</p>
                    {p.transfers.map((t, i) => (
                      <p key={`${p.plan}-2-${i}`} className="text-white/80">{t.out} → {t.in}</p>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Captain Matrix</h2>
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
    </main>
  );
}
