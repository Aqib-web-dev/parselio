import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

export function LoginSkeleton() {
  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <Skeleton className="h-6 w-40" />
      </CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </CardContent>
    </Card>
  );
}

export function LoginError({ message }: { message: string }) {
  return (
    <Alert variant="destructive" className="w-full max-w-sm">
      <AlertTitle>Sign in failed</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
