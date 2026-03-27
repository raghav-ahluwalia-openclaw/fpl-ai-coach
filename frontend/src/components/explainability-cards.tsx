"use client";

type ExplainedPlayer = {
  id: number;
  name: string;
  position: string;
  club?: string;
  price: number;
  xP: number;
  fixture_count: number;
  fixture_badge: "DGW" | "SGW" | "BLANK";
  breakdown: {
    form_score: number;
    fixture_score: number;
    minutes_security: number;
    availability_score: number;
    ownership_risk: number;
    volatility: number;
  };
  next_5_opposition?: Array<{
    gw: number;
    fixtures: Array<{ opponent: string; ha: "H" | "A"; difficulty: number }>;
    is_blank: boolean;
    is_double: boolean;
  }>;
  reason: string;
};

type ExplainabilityResponse = {
  count: number;
  players: ExplainedPlayer[];
};

const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

function difficultyClass(difficulty: number): string {
  if (difficulty <= 2) return "border-emerald-300/60 text-emerald-200 bg-emerald-500/10";
  if (difficulty === 3) return "border-amber-300/60 text-amber-200 bg-amber-500/10";
  return "border-rose-300/60 text-rose-200 bg-rose-500/10";
}

export default function ExplainabilityCards({
  explain,
  hideInTeam,
  myTeamIds,
}: {
  explain: ExplainabilityResponse | null;
  hideInTeam: boolean;
  myTeamIds: Set<number>;
}) {
  if (!explain) return null;

  return (
    <section className={`${cardClass} mt-4`}>
      <h2 className="font-semibold mb-3 text-[#00ff87]">Explainability Cards</h2>
      <div className="grid md:grid-cols-2 gap-3">
        {explain.players
          .filter((p) => !(hideInTeam && myTeamIds.has(p.id)))
          .slice(0, 8)
          .map((p) => (
            <div key={p.id} className={`border border-white/10 rounded-lg p-3 bg-black/20 text-sm ${myTeamIds.has(p.id) ? "opacity-45" : ""}`}>
              <p className="font-semibold">
                {p.name} <span className="text-white/60">({p.position}{p.club ? ` • ${p.club}` : ""})</span>
                <span
                  className={`ml-2 text-[11px] rounded-full px-2 py-0.5 border ${
                    p.fixture_badge === "DGW"
                      ? "border-emerald-300 text-emerald-200"
                      : p.fixture_badge === "BLANK"
                        ? "border-rose-300 text-rose-200"
                        : "border-white/30 text-white/80"
                  }`}
                >
                  {p.fixture_badge}
                </span>
              </p>
              <p className="text-[#00ff87] font-bold">xP {p.xP.toFixed(2)}</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-white/80 mt-1">
                <span>Form: {p.breakdown.form_score.toFixed(1)}</span>
                <span>Fixture: {p.breakdown.fixture_score.toFixed(1)}</span>
                <span>Minutes: {p.breakdown.minutes_security.toFixed(1)}</span>
                <span>Availability: {p.breakdown.availability_score.toFixed(1)}</span>
              </div>

              {p.next_5_opposition?.length ? (
                <div className="mt-2">
                  <p className="text-xs text-white/65 mb-1">Next 5 GW opposition</p>
                  <div className="space-y-1">
                    {p.next_5_opposition.map((w) => (
                      <div key={`${p.id}-${w.gw}`} className="flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] text-white/60 min-w-[42px]">GW{w.gw}</span>
                        {w.is_blank ? (
                          <span className="text-[11px] rounded-full px-2 py-0.5 border border-white/25 text-white/70">BLANK</span>
                        ) : (
                          w.fixtures.map((f, idx) => (
                            <span
                              key={`${p.id}-${w.gw}-${f.opponent}-${idx}`}
                              className={`text-[11px] rounded-full px-2 py-0.5 border ${difficultyClass(f.difficulty)}`}
                              title={`Difficulty ${f.difficulty}`}
                            >
                              {f.opponent} ({f.ha})
                            </span>
                          ))
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <p className="text-white/65 mt-2">{p.reason}</p>
            </div>
          ))}
      </div>
    </section>
  );
}
