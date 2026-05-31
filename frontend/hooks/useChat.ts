'use client';

import { useState, useCallback, useRef } from 'react';
import { ChatMessage, Citation, VideoMetadata } from '@/types';
import { sendChatMessage } from '@/services/chatService';

function generateId() {
  return Math.random().toString(36).slice(2, 10);
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef(false);

  const sendMessage = useCallback(async (
    content: string,
    sessionId: string | null,
    videoA: VideoMetadata | null,
    videoB: VideoMetadata | null
  ) => {
    if (isStreaming) return;
    if (!sessionId || !videoA || !videoB) {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: 'assistant',
          content: 'Analyze both videos first to start chatting.',
          timestamp: new Date(),
        },
      ]);
      return;
    }

    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);

    const assistantId = generateId();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
      citations: [],
    };

    setMessages((prev) => [...prev, assistantMsg]);
    setIsStreaming(true);
    abortRef.current = false;

    const history = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const stream = sendChatMessage(content, history, sessionId, videoA, videoB);

      for await (const chunk of stream) {
        if (abortRef.current) break;

        if (chunk.token) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + chunk.token }
                : m
            )
          );
        }

        if (chunk.done && chunk.citations) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, isStreaming: false, citations: chunk.citations as Citation[] }
                : m
            )
          );
        }
      }
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: 'An error occurred. Please try again.',
                isStreaming: false,
              }
            : m
        )
      );
    } finally {
      setIsStreaming(false);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false } : m
        )
      );
    }
  }, [isStreaming, messages]);

  const clearChat = useCallback(() => {
    abortRef.current = true;
    setMessages([]);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, sendMessage, clearChat };
}
