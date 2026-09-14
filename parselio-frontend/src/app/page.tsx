"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSelector } from "react-redux";
import type { RootState } from "@/store";

export default function Home() {
  const router = useRouter();
  const accessToken = useSelector((s: RootState) => s.auth.accessToken);

  useEffect(() => {
    router.replace(accessToken ? "/documents" : "/login");
  }, [accessToken, router]);

  return null;
}
