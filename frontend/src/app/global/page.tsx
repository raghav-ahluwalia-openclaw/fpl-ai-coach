"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type Pick = {
  id: number;
  name: string;
  position: string;
  price: number;
  expected_points: number;
  reason: string;
};

type GlobalRecommendation = {
  gameweek: number;
  formation: string;
  lineup: Pick[];
  captain: string;
  vice_captain: string;
  transfer_out: string;
  transfer_in: string;
  confidence: number;
  summary: string;
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

export default function GlobalPage() {
  const [data, setData] = useState<GlobalRecommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<GlobalRecommendation>(`${API_BASE}/api/fpl/recommendation`)
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load global recommendation"));
  }, []);

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-3xl font-black mb-4">Global Picks</h1>

      {error ? <p className="text-red-300">{error}</p> : null}
      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <section className={cardClass}>
          <p className="text-sm text-white/70 mb-2">
            GW {data.gameweek} • {data.formation} • Confidence {(data.confidence * 100).toFixed(0)}%
          </p>
          <p className="mb-3 text-white/85">{data.summary}</p>

          <ul className="space-y-2 mb-4">
            {data.lineup
              .sort((a, b) => b.expected_points - a.expected_points)
              .map((p) => (
                <li key={p.id} className="pb-2 border-b border-white/10 last:border-b-0">
                  <div className="font-medium">
                    {p.name} ({p.position}) — £{p.price.toFixed(1)} — {p.expected_points} xP
                  </div>
                  <div className="text-sm text-white/70">{p.reason}</div>
                </li>
              ))}
          </ul>

          <div className="rounded-md p-3 border border-white/15 bg-black/20">
            <p><strong>Captain:</strong> {data.captain}</p>
            <p><strong>Vice-captain:</strong> {data.vice_captain}</p>
            <p className="mt-2"><strong>Transfer:</strong> {data.transfer_out} → {data.transfer_in}</p>
          </div>
        </section>
      ) : null}
    </main>
  );
}
