"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api";

type AppSettings = {
  fpl_entry_id: number | null;
  entry_name?: string | null;
};

type GameweekStatus = {
  current_gw: number | null;
  next_gw: number | null;
  seconds_until_deadline: number | null;
};

function formatCountdown(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "—";
  if (seconds <= 0) return "deadline passed";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  if (d > 0) return `${d}d ${h}h`;
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export default function DecisionRail({ mode }: { mode?: string }) {
  const [entry, setEntry] = useState<string>("—");
  const [gw, setGw] = useState<string>("—");
  const [deadline, setDeadline] = useState<string>("—");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [settings, status] = await Promise.all([
          fetchJson<AppSettings>("/internal/settings", { cacheMode: "no-store" }),
          fetchJson<GameweekStatus>("/api/fpl/gameweek-status", { cacheMode: "force-cache" }),
        ]);
        if (cancelled) return;
        if (settings?.fpl_entry_id) {
          setEntry(settings.entry_name ? `${settings.entry_name}` : `Entry #${settings.fpl_entry_id}`);
        }
        setGw(`GW ${status.current_gw ?? "—"} -> ${status.next_gw ?? "—"}`);
        setDeadline(formatCountdown(status.seconds_until_deadline));
      } catch {
        // Keep silent fallback labels.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="mb-4 card-supporting text-xs md:text-sm">
      <div className="flex flex-wrap gap-2 md:gap-3 items-center text-white/85">
        <span className="pill">Entry: {entry}</span>
        <span className="pill">Mode: {mode ?? "balanced"}</span>
        <span className="pill">Window: {gw}</span>
        <span className="pill">Deadline: {deadline}</span>
      </div>
    </section>
  );
}
