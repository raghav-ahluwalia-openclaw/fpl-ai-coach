"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";

type BriefMode = "safe" | "balanced" | "aggressive";
type ModelVersion = "xgb_v1" | "xgb_hist_v1";

type NotificationSettings = {
  enabled: boolean;
  lead_hours: number;
  mode: BriefMode;
  model_version: ModelVersion;
};

type NotificationStatus = {
  enabled: boolean;
  settings: NotificationSettings;
  status: {
    is_due: boolean;
    seconds_until_deadline: number;
    deadline_utc: string;
    reminder_utc: string;
  };
  preview_message: string;
};

type NotificationTest = {
  ok: boolean;
  dry_run: boolean;
  generated_at: string;
  test_message: string;
  deadline_utc: string;
  reminder_utc: string;
};

type WeeklyBriefResponse = {
  gameweek: number;
  mode: BriefMode;
  final: {
    captain: string;
    vice_captain: string;
    transfer_out: string;
    transfer_in: string;
  };
  baseline: {
    captain: string;
    vice_captain: string;
    transfer_out: string;
    transfer_in: string;
    confidence: number;
  };
  ml: {
    captain: string;
    vice_captain: string;
    transfer_out: string;
    transfer_in: string;
    confidence: number;
    model_version: ModelVersion;
  } | null;
  creator_consensus: {
    generated_at?: string;
    top_topics: { topic: string; score: number }[];
    top_videos: { creator: string; title: string; url: string }[];
  } | null;
  rationale: string[];
};

const API_BASE = "";
const cardClass = "rounded-2xl border border-white/15 bg-white/5 backdrop-blur-md p-5";

export default function WeeklyBriefPage() {
  const [mode, setMode] = useState<BriefMode>("balanced");
  const [modelVersion, setModelVersion] = useState<ModelVersion>("xgb_hist_v1");
  const [data, setData] = useState<WeeklyBriefResponse | null>(null);
  const [notifSettings, setNotifSettings] = useState<NotificationSettings | null>(null);
  const [notifStatus, setNotifStatus] = useState<NotificationStatus | null>(null);
  const [notifSaving, setNotifSaving] = useState(false);
  const [notifTesting, setNotifTesting] = useState(false);
  const [testMessage, setTestMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<WeeklyBriefResponse>(
      `${API_BASE}/api/fpl/weekly-brief?mode=${mode}&model_version=${modelVersion}`,
    )
      .then((payload) => {
        setData(payload);
        setError(null);
      })
      .catch((e) => setError(e.message || "Failed to load weekly brief"));
  }, [mode, modelVersion]);

  useEffect(() => {
    fetchJson<NotificationSettings>(`${API_BASE}/api/fpl/notification-settings`)
      .then((payload) => setNotifSettings(payload))
      .catch(() => null);

    fetchJson<NotificationStatus>(`${API_BASE}/api/fpl/notification-status`)
      .then((payload) => setNotifStatus(payload))
      .catch(() => null);
  }, []);

  async function saveNotifications() {
    if (!notifSettings) return;
    setNotifSaving(true);
    try {
      await fetchJson<NotificationSettings>(
        `${API_BASE}/api/fpl/notification-settings?enabled=${notifSettings.enabled}&lead_hours=${notifSettings.lead_hours}&mode=${notifSettings.mode}&model_version=${notifSettings.model_version}`,
        { method: "POST" },
      );
      const status = await fetchJson<NotificationStatus>(`${API_BASE}/api/fpl/notification-status`);
      setNotifStatus(status);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save notification settings");
    } finally {
      setNotifSaving(false);
    }
  }

  async function runNotificationTest() {
    setNotifTesting(true);
    setTestMessage(null);
    try {
      const payload = await fetchJson<NotificationTest>(`${API_BASE}/api/fpl/notification-test`);
      setTestMessage(payload.test_message || "Test message generated.");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to run notification test");
    } finally {
      setNotifTesting(false);
    }
  }

  return (
    <main className="min-h-screen p-6 md:p-8 max-w-6xl mx-auto text-white">
      <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
        <h1 className="text-3xl font-black">Weekly Brief</h1>
        <div className="flex items-center gap-3 flex-wrap">
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as BriefMode)}
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
          >
            <option value="safe">Safe</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
          <select
            value={modelVersion}
            onChange={(e) => setModelVersion(e.target.value as ModelVersion)}
            className="rounded-md px-3 py-2 bg-black/30 border border-white/20"
          >
            <option value="xgb_hist_v1">Historical ML</option>
            <option value="xgb_v1">Current ML</option>
          </select>
        </div>
      </div>

      {error ? <p className="text-red-300 mb-3">{error}</p> : null}
      {!data && !error ? <p className="text-white/75">Loading...</p> : null}

      {data ? (
        <section className="grid md:grid-cols-2 gap-4">
          <div className={cardClass}>
            <p className="text-sm text-white/70 mb-2">GW {data.gameweek} • {data.mode.toUpperCase()}</p>
            <h2 className="font-semibold text-[#00ff87] mb-2">Final Action</h2>
            <p><strong>Captain:</strong> {data.final.captain}</p>
            <p><strong>Vice:</strong> {data.final.vice_captain}</p>
            <p className="mt-2"><strong>Transfer:</strong> {data.final.transfer_out} → {data.final.transfer_in}</p>
          </div>

          <div className={cardClass}>
            <h2 className="font-semibold text-[#00ff87] mb-2">Model Comparison</h2>
            <p className="text-sm text-white/80">Baseline C: {data.baseline.captain} ({Math.round(data.baseline.confidence * 100)}%)</p>
            {data.ml ? (
              <p className="text-sm text-white/80 mt-1">
                ML ({data.ml.model_version}) C: {data.ml.captain} ({Math.round(data.ml.confidence * 100)}%)
              </p>
            ) : (
              <p className="text-sm text-white/70 mt-1">ML recommendation unavailable.</p>
            )}
            <ul className="mt-3 text-sm text-white/75 space-y-1">
              {data.rationale.map((line, idx) => (
                <li key={idx}>• {line}</li>
              ))}
            </ul>
          </div>

          <div className={`${cardClass} md:col-span-2`}>
            <h2 className="font-semibold text-[#00ff87] mb-3">Deadline Notifications</h2>
            {notifSettings ? (
              <div className="grid md:grid-cols-4 gap-3 items-end">
                <label className="text-sm text-white/85 flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={notifSettings.enabled}
                    onChange={(e) => setNotifSettings({ ...notifSettings, enabled: e.target.checked })}
                  />
                  Enable reminders
                </label>

                <label className="text-sm text-white/85">
                  Lead time (hours)
                  <input
                    type="number"
                    min={1}
                    max={72}
                    value={notifSettings.lead_hours}
                    onChange={(e) =>
                      setNotifSettings({
                        ...notifSettings,
                        lead_hours: Math.max(1, Math.min(72, Number(e.target.value) || 6)),
                      })
                    }
                    className="w-full mt-1 rounded-md px-3 py-2 bg-black/30 border border-white/20"
                  />
                </label>

                <label className="text-sm text-white/85">
                  Mode
                  <select
                    value={notifSettings.mode}
                    onChange={(e) => setNotifSettings({ ...notifSettings, mode: e.target.value as BriefMode })}
                    className="w-full mt-1 rounded-md px-3 py-2 bg-black/30 border border-white/20"
                  >
                    <option value="safe">Safe</option>
                    <option value="balanced">Balanced</option>
                    <option value="aggressive">Aggressive</option>
                  </select>
                </label>

                <div className="flex gap-2">
                  <button
                    onClick={saveNotifications}
                    disabled={notifSaving}
                    className="px-4 py-2 rounded-md bg-[#00ff87] text-[#37003c] font-bold disabled:opacity-60"
                  >
                    {notifSaving ? "Saving..." : "Save Settings"}
                  </button>
                  <button
                    onClick={runNotificationTest}
                    disabled={notifTesting}
                    className="px-4 py-2 rounded-md border border-white/30 bg-black/30 text-white font-semibold disabled:opacity-60"
                  >
                    {notifTesting ? "Testing..." : "Send Test Reminder"}
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-white/70">Loading notification settings…</p>
            )}

            {notifStatus ? (
              <div className="mt-3 text-sm text-white/80 space-y-1">
                <p>
                  <strong>Next deadline:</strong> {new Date(notifStatus.status.deadline_utc).toLocaleString()}
                </p>
                <p>
                  <strong>Reminder time:</strong> {new Date(notifStatus.status.reminder_utc).toLocaleString()}
                </p>
                <p>
                  <strong>Status:</strong> {notifStatus.enabled ? (notifStatus.status.is_due ? "Reminder due now" : "Scheduled") : "Disabled"}
                </p>
                <p className="text-white/70">Preview: {notifStatus.preview_message}</p>
                {testMessage ? <p className="text-cyan-200">Test: {testMessage}</p> : null}
              </div>
            ) : null}
          </div>

          <div className={`${cardClass} md:col-span-2`}>
            <h2 className="font-semibold text-[#00ff87] mb-3">Creator Consensus</h2>
            {data.creator_consensus ? (
              <>
                <div className="flex flex-wrap gap-2 mb-4">
                  {data.creator_consensus.top_topics.map((t) => (
                    <span key={t.topic} className="text-xs rounded-full px-3 py-1 border border-white/20 bg-black/20">
                      {t.topic} ({t.score})
                    </span>
                  ))}
                </div>
                <ul className="space-y-2 text-sm text-white/80">
                  {data.creator_consensus.top_videos.map((v, idx) => (
                    <li key={`${v.url}-${idx}`} className="border border-white/10 rounded-md p-3 bg-black/20">
                      <p className="font-medium">{v.creator}</p>
                      <a href={v.url} target="_blank" rel="noreferrer" className="text-cyan-200 hover:underline">
                        {v.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="text-white/70">No consensus digest found yet. Run `./scripts/fpl_creator_digest.py`.</p>
            )}
          </div>
        </section>
      ) : null}
    </main>
  );
}
