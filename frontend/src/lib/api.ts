export type ApiErrorPayload = {
  ok?: boolean;
  error?: {
    type?: string;
    message?: string;
    status?: number;
    details?: unknown;
    timestamp?: string;
  };
};

function coerceErrorMessage(raw: string): string {
  try {
    const parsed = JSON.parse(raw) as ApiErrorPayload;
    if (parsed?.error?.message) return parsed.error.message;
    if (raw) return raw;
  } catch {
    if (raw) return raw;
  }
  return "Request failed";
}

export async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await fetch(input, {
    cache: "no-store",
    ...init,
  });

  if (!res.ok) {
    const raw = await res.text();
    throw new Error(coerceErrorMessage(raw));
  }

  return (await res.json()) as T;
}
