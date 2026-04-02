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

export async function POST(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const queryString = searchParams.toString();
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
      { error: "Server configuration missing: FPL_API_KEY or API_KEY is required for settings write." },
      { status: 503 }
    );
  }

  const backendUrl = `${backendOrigin}/api/fpl/settings${queryString ? `?${queryString}` : ""}`;

  try {
    const response = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "X-API-Key": apiKey,
        "Content-Type": "application/json",
      },
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Settings proxy error:", error);
    return NextResponse.json(
      { error: "Failed to connect to backend service" },
      { status: 502 }
    );
  }
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const queryString = searchParams.toString();
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
      { error: "Server configuration missing: FPL_API_KEY or API_KEY is required for settings reads." },
      { status: 503 },
    );
  }

  const backendUrl = `${backendOrigin}/api/fpl/settings${queryString ? `?${queryString}` : ""}`;

  try {
    const response = await fetch(backendUrl, {
      method: "GET",
      headers: {
        "X-API-Key": apiKey,
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
