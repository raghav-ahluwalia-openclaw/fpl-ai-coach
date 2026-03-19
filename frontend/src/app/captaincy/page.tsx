"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type CaptainOption = {
  id: number;
  name: string;
  position: string;
  price: number;
  xP_next_1: number;
  xP_next_3: number;
  ownership_pct: number;
  risk: number;
  form: number;
  fixture_count: number;
  fixture_badge: "DGW" | "SGW" | "BLANK";
  captain_score: number;
};

type CaptaincyLabResponse = {
  gameweek: number;
  safe_captains: CaptainOption[];
  upside_captains: CaptainOption[];
  summary: string;
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

function CaptainTable({ title, rows }: { title: string; rows: CaptainOption[] }) {
  return (
    <section className={cardClass}>
      <h2 className="font-semibold text-[#00ff87] mb-2">{title}</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-white/70 border-b border-white/10">
              <th className="py-2">#</th>
              <th className="py-2">Player</th>
              <th className="py-2">xP(1)</th>
              <th className="py-2">xP(3)</th>
              <th className="py-2">GW</th>
              <th className="py-2">Risk</th>
              <th className="py-2">Own%</th>
              <th className="py-2">Score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.id} className="border-b border-white/5">
                <td className="py-2">{i + 1}</td>
                <td className="py-2 font-medium">{r.name}</td>
                <td className="py-2">{r.xP_next_1.toFixed(2)}</td>
                <td className="py-2">{r.xP_next_3.toFixed(2)}</td>
                <td className="py-2">
                  <span
                    className={`text-xs rounded-full px-2 py-0.5 border ${
                      r.fixture_badge === "DGW"
                        ? "border-emerald-300 text-emerald-200"
                        : r.fixture_badge === "BLANK"
                          ? "border-rose-300 text-rose-200"
                          : "border-white/30 text-white/80"
                    }`}
                  >
                    {r.fixture_badge}
                  </span>
                </td>
                <td className="py-2">{r.risk.toFixed(2)}</td>
                <td className="py-2">{r.ownership_pct.toFixed(1)}</td>
                <td className="py-2 text-[#00ff87] font-semibold">{r.captain_score.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function CaptaincyPage() {
  const [limit, setLimit] = useState(10);
  const [data, setData] = useState<CaptaincyLabResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<CaptaincyLabResponse>(`${API_BASE}/api/fpl/captaincy-lab?limit=${limit}`)
      .then((payload) => {
        setData(payload);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load captaincy lab"));
  }, [limit]);

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
        <h1 className="text-3xl font-black">Captaincy Lab</h1>
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
        >
          <option value={5}>Top 5</option>
          <option value={10}>Top 10</option>
          <option value={15}>Top 15</option>
        </select>
      </div>

      {error ? <p className="text-red-300 mb-3">{error}</p> : null}
      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <section className="grid md:grid-cols-2 gap-4">
          <CaptainTable title={`Safe Captains • GW ${data.gameweek}`} rows={data.safe_captains} />
          <CaptainTable title={`Upside Captains • GW ${data.gameweek}`} rows={data.upside_captains} />
        </section>
      ) : null}
    </main>
  );
}
