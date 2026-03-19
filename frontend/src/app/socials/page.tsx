"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type SocialsResponse = {
  subreddit: string;
  reddit_window: string;
  creator_consensus: {
    generated_at?: string | null;
    top_topics: Array<{ topic: string; score: number }>;
    videos: Array<{ creator: string; title: string; url: string; summary?: string; transcript_tags?: string[] }>;
  };
  reddit_threads: Array<{ title: string; url?: string | null; score: number; num_comments: number; summary: string }>;
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

export default function SocialsPage() {
  const [data, setData] = useState<SocialsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<SocialsResponse>("/api/fpl/socials?limit=5&reddit_window=week")
      .then((payload) => {
        setData(payload);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load socials"));
  }, []);

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <h1 className="text-3xl font-black mb-4">FPL Socials</h1>

      {error ? <p className="text-red-300 mb-3">{error}</p> : null}
      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <section className="grid md:grid-cols-2 gap-4">
          <div className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-3">Creator Consensus</h2>
            {data.creator_consensus.videos.length === 0 ? (
              <p className="text-white/70">No creator digest found yet.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {data.creator_consensus.videos.map((v, idx) => (
                  <li key={`${v.url}-${idx}`} className="border border-white/10 rounded-md p-3 bg-black/20">
                    <p className="font-medium text-white/90">{v.creator}</p>
                    <a href={v.url} target="_blank" rel="noreferrer" className="text-cyan-200 hover:underline">
                      {v.title}
                    </a>
                    {v.summary ? <p className="text-white/75 mt-2">{v.summary}</p> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-3">Top 5 Reddit Threads (r/{data.subreddit})</h2>
            <ul className="space-y-3 text-sm">
              {data.reddit_threads.map((t, idx) => (
                <li key={`${t.title}-${idx}`} className="border border-white/10 rounded-md p-3 bg-black/20">
                  {t.url ? (
                    <a href={t.url} target="_blank" rel="noreferrer" className="font-medium text-cyan-200 hover:underline">
                      {idx + 1}. {t.title}
                    </a>
                  ) : (
                    <p className="font-medium">{idx + 1}. {t.title}</p>
                  )}
                  <p className="text-white/65 mt-1">👍 {t.score} • 💬 {t.num_comments}</p>
                  <p className="text-white/80 mt-2">{t.summary}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </main>
  );
}
