import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

function readEnvValueFromBackend(name: string): string {
  try {
    const envPath = path.resolve(process.cwd(), "..", "backend", ".env");
    if (!fs.existsSync(envPath)) return "";
    const raw = fs.readFileSync(envPath, "utf-8");
    const line = raw
      .split(/\r?\n/)
      .find((ln) => ln.trim().startsWith(`${name}=`));
    if (!line) return "";
    return line.split("=").slice(1).join("=").trim().replace(/^['\"]|['\"]$/g, "");
  } catch {
    return "";
  }
}

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ entry_id: string }> },
) {
  const { entry_id } = await ctx.params;
  const backendOrigin = (
    process.env.BACKEND_ORIGIN ||
    new URL(req.url).origin
  ).replace(/\/$/, "");

  const apiKey =
    process.env.FPL_API_KEY ||
    process.env.API_KEY ||
    readEnvValueFromBackend("API_KEY");

  if (!apiKey) {
    return NextResponse.json(
      { error: "Server configuration missing: FPL_API_KEY or API_KEY is required for team import." },
      { status: 503 },
    );
  }

  const backendUrl = `${backendOrigin}/api/fpl/team/${entry_id}/import`;

  try {
    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "X-API-Key": apiKey,
        "Content-Type": "application/json",
      },
    });

    const body = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";

    return new NextResponse(body, {
      status: response.status,
      headers: { "content-type": contentType },
    });
  } catch {
    return NextResponse.json({ error: "Failed to connect to backend service" }, { status: 502 });
  }
}
