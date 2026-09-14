"use client";

import { useState } from "react";
import { useSelector } from "react-redux";
import { UploadCloud } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { RootState } from "@/store";
import { decodeAccessToken } from "@/lib/decodeToken";
import { useGetUploadUrlMutation, useConfirmUploadMutation } from "@/api/apiSlice";
import { uploadDocument } from "@/features/documents/uploadDocument";

export function UploadDialog() {
  const accessToken = useSelector((s: RootState) => s.auth.accessToken);
  const [getUploadUrl] = useGetUploadUrlMutation();
  const [confirmUpload] = useConfirmUploadMutation();
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const role = accessToken ? decodeAccessToken(accessToken).company_role : undefined;
  const canUploadCompanyWide = role === "owner" || role === "admin";

  if (!canUploadCompanyWide) {
    return (
      <Card className="border-dashed bg-muted/40">
        <CardContent className="flex items-center gap-3 py-4 text-sm text-muted-foreground">
          <UploadCloud className="h-4 w-4 shrink-0" />
          Only company owners or admins can upload documents today.
        </CardContent>
      </Card>
    );
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setIsUploading(true);
    try {
      await uploadDocument(file, { visibility: "company" }, { getUploadUrl, confirmUpload });
    } catch {
      setError("Upload failed — check your role and try again.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <Card className="border-dashed">
      <CardContent className="flex items-center gap-4 py-4">
        <UploadCloud className="h-5 w-5 shrink-0 text-muted-foreground" />
        <div className="flex-1 space-y-1">
          <Input type="file" onChange={handleFileChange} disabled={isUploading} />
          {isUploading && <p className="text-xs text-muted-foreground">Uploading...</p>}
          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
