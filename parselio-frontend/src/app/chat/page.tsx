"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useChatStream } from "@/features/chat/useChatStream";
import { ChatMessageSkeleton, ChatError } from "./ChatStates";

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const { answer, isStreaming, error, sendMessage } = useChatStream();

  function handleSend() {
    if (!query.trim()) return;
    sendMessage(query, null);
    setQuery("");
  }

  return (
    <main className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-2xl flex-col px-6 py-6">
      <div className="mb-4 space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Chat</h1>
        <p className="text-sm text-muted-foreground">Ask questions about your documents.</p>
      </div>

      <Card className="flex-1 overflow-y-auto">
        <CardContent className="space-y-4 p-4">
          <div className="flex items-start gap-3">
            <Avatar className="h-8 w-8 shrink-0">
              <AvatarFallback>AI</AvatarFallback>
            </Avatar>
            <p className="rounded-lg bg-secondary px-3 py-2 text-sm text-foreground">
              Ask me anything about your documents.
            </p>
          </div>

          {answer && (
            <div className="flex items-start gap-3">
              <Avatar className="h-8 w-8 shrink-0">
                <AvatarFallback>AI</AvatarFallback>
              </Avatar>
              <p className="rounded-lg bg-secondary px-3 py-2 text-sm text-foreground">{answer}</p>
            </div>
          )}

          {isStreaming && !answer && <ChatMessageSkeleton />}

          {error && <ChatError message={error} />}
        </CardContent>
      </Card>
      <div className="mt-4 flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask a question..."
          className="flex-1"
          disabled={isStreaming}
        />
        <Button onClick={handleSend} disabled={isStreaming}>
          {isStreaming ? "Sending..." : "Send"}
        </Button>
      </div>
    </main>
  );
}
