import { useState } from "react";
import { useSelector } from "react-redux";
import type { RootState } from "../../store";

export function useChatStream() {
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<
    { number: number; chunk_id: string; document_id: string; text: string }[]
  >([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const accessToken = useSelector((s: RootState) => s.auth.accessToken);

  async function sendMessage(query: string, conversationId: string | null) {
    setAnswer("");
    setCitations([]);
    setError(null);
    setIsStreaming(true);

    try {
      const response = await fetch("http://localhost:8000/api/v1/chat/stream/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ query, conversation_id: conversationId }),
      });

      if (!response.ok || !response.body) {
        throw new Error(
          response.status === 429
            ? "Too many messages — please slow down."
            : "The server couldn't process that message."
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const blocks = buffer.split("\n\n");
        buffer = blocks.pop()!; // last (possibly incomplete) block stays in buffer

        for (const block of blocks) {
          if (block.startsWith("event: meta")) {
            const data = JSON.parse(block.split("data: ")[1]);
            setCitations(data.citations);
          } else if (block.startsWith("event: done")) {
            return;
          } else if (block.startsWith("data: ")) {
            setAnswer((prev) => prev + block.slice("data: ".length));
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsStreaming(false);
    }
  }

  return { answer, citations, isStreaming, error, sendMessage };
}
