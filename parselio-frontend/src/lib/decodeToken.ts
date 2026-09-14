export function decodeAccessToken(token: string): { company_role?: string } {
  const payload = token.split(".")[1];
  return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
}
