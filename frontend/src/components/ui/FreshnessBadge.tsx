"use client";

type FreshnessBadgeProps = {
  timestamp?: string | null;
  sourceLabel?: string;
  cacheState?: "live" | "cached" | "unknown";
  className?: string;
};

function ageMinutes(timestamp?: string | null): number | null {
  if (!timestamp) return null;
  const dt = new Date(timestamp);
  if (Number.isNaN(dt.getTime())) return null;
  return Math.max(0, Math.floor((Date.now() - dt.getTime()) / 60000));
}

function freshnessTone(minutes: number | null): string {
  if (minutes === null) return "border-white/25 text-white/75";
  if (minutes <= 30) return "border-emerald-300/50 text-emerald-200";
  if (minutes <= 180) return "border-amber-300/50 text-amber-200";
  return "border-rose-300/50 text-rose-200";
}

function freshnessText(minutes: number | null): string {
  if (minutes === null) return "freshness unknown";
  if (minutes < 1) return "updated now";
  if (minutes < 60) return `updated ${minutes}m ago`;
  const h = Math.floor(minutes / 60);
  return `updated ${h}h ago`;
}

export default function FreshnessBadge({ timestamp, sourceLabel, cacheState = "unknown", className = "" }: FreshnessBadgeProps) {
  const minutes = ageMinutes(timestamp);
  const cacheLabel = cacheState === "live" ? "live" : cacheState === "cached" ? "cached" : "state n/a";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] ${freshnessTone(minutes)} ${className}`}>
      <span>{freshnessText(minutes)}</span>
      <span className="text-white/55">•</span>
      <span>{sourceLabel || "source n/a"}</span>
      <span className="text-white/55">•</span>
      <span>{cacheLabel}</span>
    </span>
  );
}
