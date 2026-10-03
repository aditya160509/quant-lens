// Use a relative path so requests go through the Next.js proxy (no CORS, no hydration mismatch)
export const API_BASE_URL: string = process.env.NEXT_PUBLIC_API_URL || "/api";
