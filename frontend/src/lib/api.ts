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

export type FetchJsonOptions = RequestInit & {
  cacheMode?: RequestCache;
};

export async function fetchJson<T>(input: string, init?: FetchJsonOptions): Promise<T> {
  const headers = new Headers(init?.headers);

  const { cacheMode, ...rest } = init ?? {};

  const res = await fetch(input, {
    ...rest,
    cache: cacheMode ?? "default",
    headers,
  });

  if (!res.ok) {
    const raw = await res.text();
    throw new Error(coerceErrorMessage(raw));
  }

  return (await res.json()) as T;
}
