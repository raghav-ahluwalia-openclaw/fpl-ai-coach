"use client";

type HealthLevel = "good" | "warn" | "bad";

type DataHealthBannerProps = {
  level: HealthLevel;
  message: string;
  detail?: string;
  className?: string;
};

function tone(level: HealthLevel): string {
  if (level === "good") return "border-emerald-300/40 bg-emerald-300/10 text-emerald-100";
  if (level === "warn") return "border-amber-300/40 bg-amber-300/10 text-amber-100";
  return "border-rose-300/40 bg-rose-300/10 text-rose-100";
}

function icon(level: HealthLevel): string {
  if (level === "good") return "●";
  if (level === "warn") return "▲";
  return "■";
}

export default function DataHealthBanner({ level, message, detail, className = "" }: DataHealthBannerProps) {
  return (
    <section className={`rounded-xl border p-3 text-sm ${tone(level)} ${className}`} role="status" aria-live="polite">
      <p className="font-semibold">{icon(level)} Data health: {message}</p>
      {detail ? <p className="mt-1 opacity-90">{detail}</p> : null}
    </section>
  );
}
