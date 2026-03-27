"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type AppSettings = {
  scope: string;
  fpl_entry_id: number | null;
  rival_entry_id: number | null;
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-4 md:p-5";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [entryId, setEntryId] = useState("");
  const [rivalEntryId, setRivalEntryId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<AppSettings>(`${API_BASE}/api/fpl/settings`)
      .then((payload) => {
        setSettings(payload);
        setEntryId(payload.fpl_entry_id ? String(payload.fpl_entry_id) : "");
        setRivalEntryId(payload.rival_entry_id ? String(payload.rival_entry_id) : "");
      })
      .catch((e) => setError(e.message || "Failed to load settings"));
  }, []);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const qs = new URLSearchParams({ clear_missing: "true" });
      if (entryId) qs.set("fpl_entry_id", entryId);
      if (rivalEntryId) qs.set("rival_entry_id", rivalEntryId);

      const payload = await fetchJson<AppSettings>(`${API_BASE}/api/fpl/settings?${qs.toString()}`, { method: "POST" });
      setSettings(payload);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen p-3 sm:p-4 md:p-8 max-w-4xl mx-auto text-white">
      <h1 className="text-2xl sm:text-2xl sm:text-3xl font-black mb-4">Settings</h1>

      <section className={cardClass}>
        <p className="text-sm text-white/75 mb-4">
          Store your IDs once and the app will reuse them across Team, Leagues, and Planner workflows.
        </p>

        {settings ? <p className="text-xs text-white/50 mb-3">Profile scope: {settings.scope}</p> : null}

        <div className="grid md:grid-cols-2 gap-3">
          <label className="text-sm text-white/85">
            FPL Team ID
            <input
              value={entryId}
              onChange={(e) => setEntryId(e.target.value.replace(/\D/g, ""))}
              className="w-full mt-1 rounded-md h-10 px-3 bg-black/30 border border-white/20"
              inputMode="numeric"
              placeholder="e.g. 538572"
            />
          </label>

          <label className="text-sm text-white/85 md:col-span-2">
            Rival Team ID (optional)
            <input
              value={rivalEntryId}
              onChange={(e) => setRivalEntryId(e.target.value.replace(/\D/g, ""))}
              className="w-full mt-1 rounded-md h-10 px-3 bg-black/30 border border-white/20"
              inputMode="numeric"
              placeholder="Used by Planner > Rival Intelligence"
            />
          </label>
        </div>

        {!entryId && (
          <div className="flex items-center gap-2 text-amber-300 mt-4 p-3 border border-amber-300/30 rounded-lg bg-amber-300/5">
            <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current">
              <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
            </svg>
            <p className="text-sm font-medium">Please set your FPL Team ID to enable automated insights and team import.</p>
          </div>
        )}

        {error ? <p className="text-red-300 mt-3">{error}</p> : null}

        <div className="mt-4">
          <button
            onClick={save}
            disabled={saving}
            className="px-4 h-10 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60 w-full sm:w-auto"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </section>
    </main>
  );
}
