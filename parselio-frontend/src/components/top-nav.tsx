"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSelector, useDispatch } from "react-redux";
import { FileStack, FileText, MessageSquare, LogOut } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/theme-toggle";
import type { RootState } from "@/store";
import { loggedOut } from "@/features/auth/authSlice";
import { decodeAccessToken } from "@/lib/decodeToken";

const NAV_LINKS = [
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/chat", label: "Chat", icon: MessageSquare },
];

export function TopNav() {
  const pathname = usePathname();
  const router = useRouter();
  const dispatch = useDispatch();
  const accessToken = useSelector((s: RootState) => s.auth.accessToken);
  const role = accessToken ? decodeAccessToken(accessToken).company_role : undefined;

  function handleLogout() {
    dispatch(loggedOut());
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
        <Link href={accessToken ? "/documents" : "/login"} className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary/70 text-primary-foreground shadow-sm shadow-primary/30">
            <FileStack className="h-4 w-4" strokeWidth={2.25} />
          </span>
          <span className="text-sm font-semibold tracking-tight text-foreground">Parselio</span>
        </Link>

        {accessToken && (
          <nav className="hidden items-center gap-1 sm:flex">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => {
              const isActive = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors " +
                    (isActive
                      ? "bg-secondary text-foreground"
                      : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground")
                  }
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </nav>
        )}

        <div className="flex items-center gap-3">
          {accessToken ? (
            <>
              {role && (
                <Badge variant="outline" className="hidden capitalize sm:inline-flex">
                  {role}
                </Badge>
              )}
              <ThemeToggle />
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Log out</span>
              </Button>
            </>
          ) : (
            <>
              <ThemeToggle />
              <Link href="/login" className={buttonVariants({ size: "sm" })}>
                Sign in
              </Link>
            </>
          )}
        </div>
      </div>

      {accessToken && (
        <nav className="flex items-center gap-1 border-t border-border px-4 py-1.5 sm:hidden">
          {NAV_LINKS.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={
                  "flex flex-1 items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium transition-colors " +
                  (isActive
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground")
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      )}
    </header>
  );
}
