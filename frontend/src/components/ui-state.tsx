"use client";

type BaseStateProps = {
  className?: string;
};

export function LoadingState({
  label = "Loading...",
  className = "",
}: { label?: string } & BaseStateProps) {
  return (
    <section
      role="status"
      aria-live="polite"
      aria-busy="true"
      className={`rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5 animate-fade-in ${className}`}
    >
      <p className="text-white/80 text-sm">{label}</p>
      <div className="mt-3 space-y-2 animate-pulse">
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
  className = "",
}: {
  message: string;
  onRetry?: () => void;
} & BaseStateProps) {
  return (
    <section
      role="alert"
      aria-live="assertive"
      className={`rounded-2xl border border-rose-300/40 bg-rose-400/5 backdrop-blur-md p-4 md:p-5 animate-fade-in ${className}`}
    >
      <h3 className="text-rose-100 font-semibold text-sm">Something went wrong</h3>
      <p className="text-rose-200 text-sm mt-1">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 h-9 px-3 rounded-md border border-rose-300/50 text-rose-100 hover:bg-rose-400/10 transition-colors"
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
  className = "",
}: {
  title: string;
  description?: string;
  onRetry?: () => void;
} & BaseStateProps) {
  return (
    <section
      role="status"
      aria-live="polite"
      className={`rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5 animate-fade-in ${className}`}
    >
      <h3 className="text-white font-semibold">{title}</h3>
      {description ? <p className="text-white/70 text-sm mt-1">{description}</p> : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 h-9 px-3 rounded-md border border-white/25 text-white/90 hover:border-[#00ff87] hover:text-[#00ff87] transition-colors"
        >
          Retry
        </button>
      ) : null}
    </section>
  );
}
