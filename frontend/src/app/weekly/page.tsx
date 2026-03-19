"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchJson } from "@/lib/api";

type Mode = "safe" | "balanced" | "aggressive";

type AppSettings = { fpl_entry_id: number | null };

type HealthRow = {
  name: string;
  position: string;
  projected_points_3: number;
  minutes_risk: number;
  availability_risk: number;
  fixture_badge: "DGW" | "SGW" | "BLANK";
  injury_news: string;
  upside_safety_score: number;
};

type TransferMove = {
  out: string;
  in: string;
  gain: number;
  projected_points_3_in: number;
  projected_points_3_out: number;
  fixture_difficulty_factor_in: number;
  minutes_risk_in: number;
  availability_risk_in: number;
  injury_news_in: string;
  upside_safety_score_in: number;
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
};

type WeeklyCockpit = {
  entry_id: number;
  gameweek: number;
  mode: Mode;
  lineup_optimizer: {
    formation: string;
    starting_xi: Array<{ name: string; position: string; xP_next_1: number; xP_next_3: number; fixture_badge: "DGW" | "SGW" | "BLANK" }>;
    bench_order: Array<{ name: string; position: string; bench_rank: number; xP_next_1: number; xP_next_3: number; fixture_badge: "DGW" | "SGW" | "BLANK" }>;
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
  summary: string;
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

export default function WeeklyPage() {
  const [teamId, setTeamId] = useState("");
  const [mode, setMode] = useState<Mode>("balanced");
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
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-3xl font-black mb-4">Weekly Cockpit</h1>

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
            onClick={() => void run()}
            disabled={loading || !/^\d+$/.test(teamId.trim())}
            className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60"
          >
            {loading ? "Loading..." : "Run Weekly Plan"}
          </button>
        </div>
      </section>

      {error ? <p className="text-red-300 mb-4">{error}</p> : null}

      {data ? (
        <div className="space-y-6">
          <section className={cardClass}>
            <h2 className="text-xl font-bold text-[#00ff87] mb-3">Lineup Optimizer</h2>
            <p className="text-sm text-white/75 mb-3">Recommended formation: <span className="font-semibold text-white">{data.lineup_optimizer.formation}</span></p>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <div className="rounded-lg border border-white/10 p-3 bg-black/20">
                <h3 className="font-semibold mb-2">Starting XI</h3>
                <ul className="space-y-1">
                  {data.lineup_optimizer.starting_xi.map((p) => (
                    <li key={`xi-${p.name}`}>
                      {p.name} ({p.position}) • xP1 {p.xP_next_1} • xP3 {p.xP_next_3} • {p.fixture_badge}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-white/10 p-3 bg-black/20">
                <h3 className="font-semibold mb-2">Bench Order</h3>
                <ul className="space-y-1">
                  {data.lineup_optimizer.bench_order.map((p) => (
                    <li key={`bench-${p.name}`}>
                      {p.bench_rank}. {p.name} ({p.position}) • xP1 {p.xP_next_1} • xP3 {p.xP_next_3} • {p.fixture_badge}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="text-xl font-bold text-[#00ff87] mb-3">Your Team Health</h2>
            <div className="grid md:grid-cols-3 gap-4">
              {["sell", "watch", "hold"].map((bucket) => (
                <div key={bucket} className="rounded-lg border border-white/10 p-3 bg-black/20">
                  <h3 className="font-semibold uppercase text-sm mb-2">{bucket}</h3>
                  <ul className="space-y-2 text-sm">
                    {(data.team_health[bucket as keyof typeof data.team_health] as HealthRow[]).map((p) => (
                      <li key={`${bucket}-${p.name}`}>
                        <div className="font-medium">{p.name} ({p.position}) • xP3 {p.projected_points_3}</div>
                        <div className="text-white/70">Risk M:{p.minutes_risk} A:{p.availability_risk} • {p.fixture_badge}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="text-xl font-bold text-[#00ff87] mb-3">Top Transfer Plans (Plan A/B/C)</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <h3 className="font-semibold mb-2">1FT</h3>
                <ul className="space-y-3 text-sm">
                  {data.top_transfer_plans.one_ft.map((p) => (
                    <li key={`1ft-${p.plan}`} className="rounded-lg border border-white/10 p-3 bg-black/20">
                      <div className="font-medium">{p.plan} • Net {p.net_gain} • Hit {p.hit}</div>
                      {p.transfers.map((t, i) => (
                        <div key={`${p.plan}-1-${i}`} className="text-white/80">{t.out} → {t.in} (gain {t.gain}, xP3 {t.projected_points_3_out}→{t.projected_points_3_in})</div>
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="font-semibold mb-2">2FT</h3>
                <ul className="space-y-3 text-sm">
                  {data.top_transfer_plans.two_ft.map((p) => (
                    <li key={`2ft-${p.plan}`} className="rounded-lg border border-white/10 p-3 bg-black/20">
                      <div className="font-medium">{p.plan} • Net {p.net_gain} • Hit {p.hit}</div>
                      {p.transfers.map((t, i) => (
                        <div key={`${p.plan}-2-${i}`} className="text-white/80">{t.out} → {t.in} (gain {t.gain}, xP3 {t.projected_points_3_out}→{t.projected_points_3_in})</div>
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="text-xl font-bold text-[#00ff87] mb-3">Captain Matrix</h2>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <div>
                <h3 className="font-semibold mb-2">Safe</h3>
                <ul className="space-y-2">
                  {data.captain_matrix.safe.map((c) => (
                    <li key={`safe-${c.name}`}>{c.name} • score {c.safe_score} • xP3 {c.projected_points_3}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="font-semibold mb-2">Differential</h3>
                <ul className="space-y-2">
                  {data.captain_matrix.differential.map((c) => (
                    <li key={`diff-${c.name}`}>{c.name} • score {c.differential_score} • own {c.ownership_pct}%</li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="text-xl font-bold text-[#00ff87] mb-3">What Changed Since Last Week</h2>
            <div className="space-y-3 text-sm">
              {data.what_changed.length === 0 ? <p className="text-white/70">No major changes detected.</p> : null}
              {data.what_changed.map((item, idx) => {
                const type = String(item.type ?? "update");
                const summary = String(item.summary ?? "Update");
                if (type === "squad_changes") {
                  const outs = Array.isArray(item.out) ? (item.out as string[]) : [];
                  const ins = Array.isArray(item.in) ? (item.in as string[]) : [];
                  return (
                    <div key={`chg-${idx}`} className="rounded-lg border border-white/10 p-3 bg-black/20">
                      <p className="font-medium">{summary}</p>
                      <p className="text-white/80">Out: {outs.join(", ") || "—"}</p>
                      <p className="text-white/80">In: {ins.join(", ") || "—"}</p>
                    </div>
                  );
                }
                if (type === "injury_news") {
                  const players = Array.isArray(item.players) ? (item.players as Array<{ name?: string; news?: string }>) : [];
                  return (
                    <div key={`chg-${idx}`} className="rounded-lg border border-white/10 p-3 bg-black/20">
                      <p className="font-medium">{summary}</p>
                      <ul className="mt-1 space-y-1 text-white/80">
                        {players.map((p, i) => (
                          <li key={`inj-${idx}-${i}`}>{p.name || "Player"}: {p.news || "No details"}</li>
                        ))}
                      </ul>
                    </div>
                  );
                }
                if (type === "fixture_swings") {
                  const players = Array.isArray(item.players)
                    ? (item.players as Array<{ name?: string; from?: string; to?: string }>)
                    : [];
                  return (
                    <div key={`chg-${idx}`} className="rounded-lg border border-white/10 p-3 bg-black/20">
                      <p className="font-medium">{summary}</p>
                      <ul className="mt-1 space-y-1 text-white/80">
                        {players.map((p, i) => (
                          <li key={`fix-${idx}-${i}`}>{p.name || "Player"}: {p.from || "?"} → {p.to || "?"}</li>
                        ))}
                      </ul>
                    </div>
                  );
                }
                return (
                  <div key={`chg-${idx}`} className="rounded-lg border border-white/10 p-3 bg-black/20">
                    <p className="font-medium">{summary}</p>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
