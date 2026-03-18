import Link from "next/link";

const cards = [
  {
    title: "Global Picks",
    desc: "Model-driven XI, captaincy and transfer ideas for the wider player pool.",
    href: "/global",
  },
  {
    title: "Target Radar",
    desc: "Safe targets + differential targets across upcoming gameweeks.",
    href: "/targets",
  },
  {
    title: "Top Players",
    desc: "See the highest projected players for the next gameweek.",
    href: "/top",
  },
  {
    title: "My Team",
    desc: "Import your FPL team and get personalized lineup + transfer guidance.",
    href: "/team",
  },
  {
    title: "Rank Trend",
    desc: "Visualize overall rank gameweek by gameweek and spot momentum shifts.",
    href: "/team-rank",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <section className="mb-8 rounded-2xl p-6 md:p-8 border border-white/20 bg-gradient-to-r from-[#37003c] via-[#5f0f78] to-[#e90052] shadow-2xl">
        <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/90 mb-2">Fantasy Premier League</p>
        <h1 className="text-3xl md:text-4xl font-black">FPL AI Coach</h1>
        <p className="text-sm md:text-base text-white/85 mt-2">
          Choose a feature page to run team analysis, transfer targets, and ranking insights.
        </p>
      </section>

      <section className="grid md:grid-cols-2 gap-4">
        {cards.map((card) => (
          <Link
            key={card.href}
            href={card.href}
            className="rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5 hover:border-[#00ff87]/60 hover:bg-white/10 transition"
          >
            <h2 className="text-xl font-bold mb-2 text-[#00ff87]">{card.title}</h2>
            <p className="text-white/80">{card.desc}</p>
          </Link>
        ))}
      </section>
    </main>
  );
}
