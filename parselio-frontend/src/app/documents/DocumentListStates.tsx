import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

export function DocumentListSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3].map((i) => (
        <Card key={i}>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-4 w-16" />
          </CardHeader>
        </Card>
      ))}
    </div>
  );
}

export function DocumentListError({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>Couldn&apos;t load documents</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
