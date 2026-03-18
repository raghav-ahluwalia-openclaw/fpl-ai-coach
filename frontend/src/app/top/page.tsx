"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type TopPlayer = {
  id: number;
  name: string;
  position: string;
  team_id: number;
  price: number;
  xP: number;
  form: number;
  ppg: number;
};

type TopPlayersResponse = {
  count: number;
  next_gw: number;
  players: TopPlayer[];
  last_ingested_at?: string;
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

export default function TopPage() {
  const [limit, setLimit] = useState(20);
  const [data, setData] = useState<TopPlayersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<TopPlayersResponse>(`${API_BASE}/api/fpl/top?limit=${limit}`)
      .then((payload) => {
        setData(payload);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load top players"));
  }, [limit]);

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
        <h1 className="text-3xl font-black">Top Players</h1>
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
        >
          <option value={10}>Top 10</option>
          <option value={20}>Top 20</option>
          <option value={30}>Top 30</option>
          <option value={50}>Top 50</option>
        </select>
      </div>

      {error ? <p className="text-red-300 mb-3">{error}</p> : null}
      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <section className={cardClass}>
          <p className="text-sm text-white/75 mb-3">
            GW {data.next_gw} • Showing {data.count} players
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-white/70 border-b border-white/10">
                  <th className="py-2">#</th>
                  <th className="py-2">Player</th>
                  <th className="py-2">Pos</th>
                  <th className="py-2">Price</th>
                  <th className="py-2">xP</th>
                  <th className="py-2">Form</th>
                  <th className="py-2">PPG</th>
                </tr>
              </thead>
              <tbody>
                {data.players.map((p, idx) => (
                  <tr key={p.id} className="border-b border-white/5">
                    <td className="py-2">{idx + 1}</td>
                    <td className="py-2 font-medium">{p.name}</td>
                    <td className="py-2">{p.position}</td>
                    <td className="py-2">£{p.price.toFixed(1)}</td>
                    <td className="py-2 text-[#00ff87] font-semibold">{p.xP.toFixed(2)}</td>
                    <td className="py-2">{p.form.toFixed(1)}</td>
                    <td className="py-2">{p.ppg.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </main>
  );
}
