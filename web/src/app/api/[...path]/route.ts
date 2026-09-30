// Same-origin proxy to the Python API. Keeps the API URL a runtime setting
// (API_URL) and avoids CORS in the browser.

import type { NextRequest } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

type Ctx = { params: Promise<{ path: string[] }> };

async function proxy(req: NextRequest, { params }: Ctx) {
  const { path } = await params;
  const target = `${API_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const hasBody = !["GET", "HEAD"].includes(req.method);

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers: { "Content-Type": req.headers.get("content-type") ?? "application/json" },
      body: hasBody ? await req.text() : undefined,
      cache: "no-store",
    });
    return new Response(upstream.status === 204 ? null : upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json({ detail: `API unreachable at ${API_URL}` }, { status: 502 });
  }
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
