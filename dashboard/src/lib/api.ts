import { z } from "zod";

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
export function token(): string {
  return typeof window === "undefined"
    ? ""
    : (sessionStorage.getItem("tracelore.token") ?? "");
}
export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
      ...init.headers,
    },
  });
  const payload: unknown = await response.json();
  if (!response.ok) {
    const failure = z
      .object({ error: z.object({ code: z.string(), message: z.string() }) })
      .safeParse(payload);
    if (response.status === 401 && path !== "/auth/token") {
      sessionStorage.removeItem("tracelore.token");
      window.dispatchEvent(new Event("tracelore:unauthorized"));
    }
    throw new ApiError(
      failure.success ? failure.data.error.code : "HTTP_ERROR",
      failure.success
        ? failure.data.error.message
        : `Request failed (${response.status})`,
      response.status,
    );
  }
  return schema.parse(payload);
}
