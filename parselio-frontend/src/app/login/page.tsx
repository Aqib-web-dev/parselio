"use client";

import { useState } from "react";
import { useDispatch } from "react-redux";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { AmbientBackground } from "@/components/ambient-background";
import { useLoginMutation } from "@/api/apiSlice";
import { loggedIn } from "@/features/auth/authSlice";
import { LoginError } from "./LoginError"; // moved out of page.tsx in Step 3

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [login, { isLoading, error }] = useLoginMutation();
  const dispatch = useDispatch();
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const data = await login({ username, password }).unwrap();
      dispatch(loggedIn(data));
      router.push("/documents");
    } catch {
      // error is already captured by the error field above — nothing else to do here
    }
  }

  return (
    <main className="relative isolate flex min-h-[calc(100vh-3.5rem)] items-center justify-center overflow-hidden bg-background p-4">
      <AmbientBackground />
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4">
        {error && (
          <LoginError
            message={
              "status" in error && error.status === 401
                ? "Wrong username or password."
                : "Something went wrong. Please try again."
            }
          />
        )}
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-xl">Sign in to Parselio</CardTitle>
            <p className="text-sm text-muted-foreground">
              Enter your credentials to access your workspace.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              disabled={isLoading}
              autoFocus
            />
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              disabled={isLoading}
            />
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Signing in..." : "Sign in"}
            </Button>
          </CardContent>
        </Card>
      </form>
    </main>
  );
}
