import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";

export function ChatMessageSkeleton() {
  return (
    <div className="flex items-start gap-3">
      <Skeleton className="h-8 w-8 rounded-full" />
      <div className="space-y-2 flex-1">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    </div>
  );
}

export function ChatError({ message }: { message: string }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>Message failed to send</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
