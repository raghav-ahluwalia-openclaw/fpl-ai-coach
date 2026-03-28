"use client";

export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <section className="rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5 animate-pulse">
      <p className="text-white/80 text-sm">{label}</p>
      <div className="mt-3 space-y-2">
        <div className="h-3 w-2/3 bg-white/10 rounded" />
        <div className="h-3 w-1/2 bg-white/10 rounded" />
        <div className="h-3 w-3/4 bg-white/10 rounded" />
      </div>
    </section>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <section className="rounded-2xl border border-rose-300/40 bg-rose-400/5 backdrop-blur-md p-4 md:p-5">
      <p className="text-rose-200 text-sm">{message}</p>
      {onRetry ? (
        <button
          onClick={onRetry}
          className="mt-3 h-9 px-3 rounded-md border border-rose-300/50 text-rose-100 hover:bg-rose-400/10"
        >
          Retry
        </button>
      ) : null}
    </section>
  );
}

export function EmptyState({
  title,
  description,
  onRetry,
}: {
  title: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <section className="rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5">
      <h3 className="text-white font-semibold">{title}</h3>
      {description ? <p className="text-white/70 text-sm mt-1">{description}</p> : null}
      {onRetry ? (
        <button
          onClick={onRetry}
          className="mt-3 h-9 px-3 rounded-md border border-white/25 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87]"
        >
          Retry
        </button>
      ) : null}
    </section>
  );
}
