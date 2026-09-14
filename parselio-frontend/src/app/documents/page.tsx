"use client";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useListDocumentsQuery } from "@/api/apiSlice";
import { DocumentListSkeleton, DocumentListError } from "./DocumentListStates";
import { UploadDialog } from "./UploadDialog";

const STATUS_VARIANT: Record<string, "secondary" | "outline" | "destructive"> = {
  ready: "secondary",
  processing: "outline",
  uploaded: "outline",
  failed: "destructive",
};

export default function DocumentsPage() {
  const { data, isLoading, error } = useListDocumentsQuery(undefined, {
    pollingInterval: 3000,
    skipPollingIfUnfocused: true,
  });

  return (
    <main className="mx-auto max-w-2xl space-y-6 px-6 py-10">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Documents</h1>
        <p className="text-sm text-muted-foreground">
          Company-wide and team documents available to you.
        </p>
      </div>

      <UploadDialog />

      {error && (
        <DocumentListError message="Couldn't reach the server. Check your connection and try again." />
      )}

      {!error && isLoading && <DocumentListSkeleton />}

      {!error &&
        !isLoading &&
        data &&
        (data.results.length === 0 ? (
          <Card className="border-dashed">
            <CardHeader className="items-center text-center">
              <CardTitle className="text-sm font-normal text-muted-foreground">
                No documents yet — upload one above to get started.
              </CardTitle>
            </CardHeader>
          </Card>
        ) : (
          <div className="space-y-2">
            {data.results.map((doc) => (
              <Card key={doc.id} className="transition-colors hover:bg-secondary/40">
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle className="text-sm font-medium">{doc.title}</CardTitle>
                  <Badge variant={STATUS_VARIANT[doc.status] ?? "outline"} className="capitalize">
                    {doc.status}
                  </Badge>
                </CardHeader>
              </Card>
            ))}
          </div>
        ))}
    </main>
  );
}
