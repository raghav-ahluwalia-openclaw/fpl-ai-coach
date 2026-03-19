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
            <pre className="text-xs text-white/80 whitespace-pre-wrap">{JSON.stringify(data.what_changed, null, 2)}</pre>
          </section>
        </div>
      ) : null}
    </main>
  );
}
