"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { fetchJson } from "@/lib/api";
import { ErrorState, LoadingState } from "@/components/ui-state";

type Mode = "safe" | "balanced" | "aggressive";

type AppSettings = {
  fpl_entry_id: number | null;
};

type Band = {
  mean: number;
  p10: number;
  p50: number;
  p90: number;
  samples: number;
  prob_10_plus?: number;
  prob_blank_2_or_less?: number;
  prob_positive?: number;
  prob_4_plus?: number;
  prob_minus_4_or_worse?: number;
};

type CaptainBand = {
  id: number;
  name: string;
  position: string;
  projected_points_1: number;
  risk_score: number;
  band: Band;
};

type TransferBand = {
  plan: string;
  transfer_count: number;
  hit: number;
  net_gain_mean_input: number;
  moves: string[];
  band: Band;
};

type SimulationPayload = {
  entry_id: number;
  gameweek: number;
  mode: Mode;
  schema: string;
  generated_at: string;
  settings: {
    iterations: number;
    captain_limit: number;
    transfer_limit: number;
  };
  captain_outcome_bands: CaptainBand[];
  transfer_outcome_bands: TransferBand[];
  summary: string;
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

export default function SimulationPage() {
  const [entryId, setEntryId] = useState<number>(0);
  const [mode, setMode] = useState<Mode>("balanced");
  const [iterations, setIterations] = useState<number>(1500);

  const [data, setData] = useState<SimulationPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (id: number, currentMode: Mode, currentIterations: number) => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchJson<SimulationPayload>(
        `/api/fpl/team/${id}/simulation-lab?mode=${currentMode}&iterations=${currentIterations}`,
        { cacheMode: "no-store" }
      );
      setData(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load simulation lab");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const settings = await fetchJson<AppSettings>("/internal/settings", { cacheMode: "no-store" });
        const id = Number(settings?.fpl_entry_id || 0);
        if (!mounted) return;
        if (!id) {
          setLoading(false);
          setError("Set your FPL Entry ID in Settings first.");
          return;
        }
        setEntryId(id);
        await load(id, mode, iterations);
      } catch (e) {
        if (!mounted) return;
        setLoading(false);
        setError(e instanceof Error ? e.message : "Could not read settings");
      }
    })();
    return () => {
      mounted = false;
    };
  }, [load, mode, iterations]);

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-6xl mx-auto text-white">
      <section className="mb-6 rounded-2xl p-4 sm:p-6 border border-white/20 bg-gradient-to-r from-[#1f0030] via-[#37003c] to-[#4b006e]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-200/90 mb-2">Simulation Lab</p>
            <h1 className="text-2xl md:text-3xl font-black">Monte Carlo Outcome Bands</h1>
            <p className="text-white/80 mt-1 text-sm md:text-base">Captain + transfer decision ranges for your next GW.</p>
          </div>
          <Link href="/weekly" className="rounded-lg border border-white/25 px-3 py-2 text-sm hover:border-[#00ff87] hover:text-[#00ff87]">
            ← Back to Weekly Hub
          </Link>
        </div>
      </section>

      <section className={`${cardClass} mb-6`}>
        <div className="flex flex-wrap gap-3 items-end">
          <label className="grid gap-1 text-sm">
            <span className="text-white/70">Entry ID</span>
            <input
              className="rounded-md bg-black/30 border border-white/25 px-3 py-2"
              type="number"
              value={entryId || ""}
              onChange={(e) => setEntryId(Number(e.target.value || 0))}
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-white/70">Mode</span>
            <select className="rounded-md bg-black/30 border border-white/25 px-3 py-2" value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
              <option value="safe">safe</option>
              <option value="balanced">balanced</option>
              <option value="aggressive">aggressive</option>
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-white/70">Iterations</span>
            <select
              className="rounded-md bg-black/30 border border-white/25 px-3 py-2"
              value={iterations}
              onChange={(e) => setIterations(Number(e.target.value))}
            >
              <option value={500}>500</option>
              <option value={1000}>1000</option>
              <option value={1500}>1500</option>
              <option value={2500}>2500</option>
            </select>
          </label>
          <button
            className="rounded-md bg-[#00ff87] text-[#37003c] font-bold px-4 py-2 hover:bg-[#00e676]"
            onClick={() => entryId && load(entryId, mode, iterations)}
          >
            Re-run
          </button>
        </div>
      </section>

      {loading ? <LoadingState label="Running simulations…" /> : null}
      {!loading && error ? <ErrorState message={error} /> : null}

      {!loading && !error && data ? (
        <>
          <section className={`${cardClass} mb-6`}>
            <p className="text-white/80">{data.summary}</p>
            <p className="text-xs text-white/55 mt-2">GW {data.gameweek} • {new Date(data.generated_at).toLocaleString()} • {data.settings.iterations} simulations per option</p>
          </section>

          <section className={`${cardClass} mb-6`}>
            <h2 className="text-xl font-bold text-[#00ff87] mb-3">Captain bands (2x captain points)</h2>
            <div className="space-y-3">
              {data.captain_outcome_bands.map((c) => (
                <div key={c.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="flex flex-wrap justify-between gap-2 mb-2">
                    <p className="font-semibold">{c.name} <span className="text-white/60 text-sm">({c.position})</span></p>
                    <p className="text-sm text-white/70">risk {Math.round(c.risk_score * 100)}%</p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-sm">
                    <p>P10: <span className="font-semibold">{c.band.p10}</span></p>
                    <p>P50: <span className="font-semibold">{c.band.p50}</span></p>
                    <p>P90: <span className="font-semibold">{c.band.p90}</span></p>
                    <p>Mean: <span className="font-semibold">{c.band.mean}</span></p>
                    <p>10+: <span className="font-semibold">{Math.round((c.band.prob_10_plus || 0) * 100)}%</span></p>
                    <p>Blank≤2: <span className="font-semibold">{Math.round((c.band.prob_blank_2_or_less || 0) * 100)}%</span></p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className={cardClass}>
            <h2 className="text-xl font-bold text-[#00ff87] mb-3">Transfer bands (net gain)</h2>
            <div className="space-y-3">
              {data.transfer_outcome_bands.map((t) => (
                <div key={t.plan} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="flex flex-wrap justify-between gap-2 mb-2">
                    <p className="font-semibold">{t.plan} <span className="text-white/60 text-sm">({t.transfer_count} transfer{t.transfer_count > 1 ? "s" : ""}, hit {t.hit})</span></p>
                    <p className="text-sm text-white/70">input net {t.net_gain_mean_input}</p>
                  </div>
                  <p className="text-sm text-white/80 mb-2">{t.moves.join(" • ") || "Roll transfer"}</p>
                  <div className="grid grid-cols-2 md:grid-cols-7 gap-2 text-sm">
                    <p>P10: <span className="font-semibold">{t.band.p10}</span></p>
                    <p>P50: <span className="font-semibold">{t.band.p50}</span></p>
                    <p>P90: <span className="font-semibold">{t.band.p90}</span></p>
                    <p>Mean: <span className="font-semibold">{t.band.mean}</span></p>
                    <p>Positive: <span className="font-semibold">{Math.round((t.band.prob_positive || 0) * 100)}%</span></p>
                    <p>4+: <span className="font-semibold">{Math.round((t.band.prob_4_plus || 0) * 100)}%</span></p>
                    <p>-4 or worse: <span className="font-semibold">{Math.round((t.band.prob_minus_4_or_worse || 0) * 100)}%</span></p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      ) : null}
    </main>
  );
}
