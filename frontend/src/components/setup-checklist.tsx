"use client";

import Link from "next/link";

type SetupChecklistProps = {
  teamId: number | string | null;
  rivalId: number | string | null;
  weeklyLoaded: boolean;
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

export function SetupChecklist({ teamId, rivalId, weeklyLoaded }: SetupChecklistProps) {
  const items = [
    {
      label: "FPL Team ID",
      done: !!teamId,
      cta: "/settings",
      ctaLabel: "Configure",
      desc: "Connect your team to get personalized insights.",
    },
    {
      label: "Weekly Hub",
      done: weeklyLoaded,
      cta: "/weekly",
      ctaLabel: "Load Hub",
      desc: "Fetch your latest squad data and projections.",
    },
    {
      label: "Rival Analysis",
      done: !!rivalId,
      cta: "/settings",
      ctaLabel: "Optional",
      desc: "Add a rival ID to track competitive differentials.",
      optional: true,
    },
  ];

  const allDone = items.filter(i => !i.optional).every(i => i.done);

  return (
    <section className={cardClass}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          Setup Progress
          {allDone && <span className="text-[10px] bg-[#00ff87]/20 text-[#00ff87] px-2 py-0.5 rounded-full uppercase tracking-wider">Ready</span>}
        </h2>
      </div>

      <div className="space-y-4">
        {items.map((item) => (
          <div key={item.label} className="flex items-start gap-3">
            <div className="mt-0.5">
              {item.done ? (
                <svg className="h-5 w-5 text-[#00ff87]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              ) : (
                <svg className="h-5 w-5 text-white/30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                </svg>
              )}
            </div>
            <div className="flex-1 text-left">
              <div className="flex items-center justify-between">
                <span className={`text-sm font-semibold ${item.done ? "text-white" : "text-white/60"}`}>
                  {item.label}
                  {item.optional && <span className="ml-2 text-[10px] text-white/40 font-normal italic">(Optional)</span>}
                </span>
                {!item.done && (
                  <Link
                    href={item.cta}
                    className="text-[11px] font-bold text-[#00ff87] hover:underline flex items-center gap-0.5"
                  >
                    {item.ctaLabel} 
                    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </Link>
                )}
              </div>
              <p className="text-xs text-white/50">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
