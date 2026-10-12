"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MacroBar } from "@/components/macro-bar";
import { Button } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { cn, num, time } from "@/lib/format";
import type { ChatMessage, ChatResponse, Conversation, Page } from "@/lib/types";

type Msg = ChatMessage & { pending?: boolean; failed?: boolean };
type Payload = { status?: string; result?: Record<string, unknown> | null; options?: { id: string; name: string }[] | null };

const SUGGESTIONS = [
  "I ate 3 eggs and 200g rice for breakfast",
  "Bench press 60kg 4x8",
  "I drank 750ml water",
  "My weight today is 66.8kg",
  "How much protein have I eaten today?",
  "What is today's workout?",
];

function payloadOf(m: Msg): Payload {
  if (m.result !== undefined || m.options !== undefined) return { status: m.status, result: m.result, options: m.options };
  return ((m as unknown as { parsed_payload?: Payload }).parsed_payload ?? {}) as Payload;
}

export default function ChatPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const convs = await api<Page<Conversation>>(`/chat/conversations${qs({ page_size: 1 })}`);
        const latest = convs.items[0];
        if (latest) {
          const msgs = await api<Page<ChatMessage>>(`/chat/conversations/${latest.id}/messages${qs({ page_size: 60 })}`);
          setConversationId(latest.id);
          setMessages([...msgs.items].reverse());
        }
      } catch {
        /* empty state is fine */
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const send = useCallback(
    async (raw: string) => {
      const message = raw.trim();
      if (!message || sending) return;
      setSending(true);
      setText("");
      const tempId = `tmp-${Date.now()}`;
      const now = new Date().toISOString();
      setMessages((m) => [
        ...m,
        { id: tempId, role: "user", content: message, parsed_intent: null, created_at: now },
        { id: `${tempId}-a`, role: "assistant", content: "", parsed_intent: null, created_at: now, pending: true },
      ]);
      try {
        const res = await api<ChatResponse>("/chat/messages", { body: { message, conversation_id: conversationId } });
        setConversationId(res.conversation_id);
        setMessages((m) =>
          m.map((x) =>
            x.id === `${tempId}-a`
              ? {
                  id: res.message_id, role: "assistant", content: res.message, parsed_intent: res.intent,
                  created_at: new Date().toISOString(), result: res.result, status: res.status,
                  options: res.clarification?.options ?? null,
                }
              : x,
          ),
        );
      } catch (e) {
        setMessages((m) =>
          m.map((x) => (x.id === `${tempId}-a` ? { ...x, pending: false, failed: true, content: (e as Error).message } : x)),
        );
      } finally {
        setSending(false);
        input.current?.focus();
      }
    },
    [conversationId, sending],
  );

  function newChat() {
    setConversationId(null);
    setMessages([]);
    input.current?.focus();
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const lastOptions = lastAssistant ? payloadOf(lastAssistant).options : null;

  return (
    <div className="mx-auto flex h-[calc(100dvh-7.5rem)] max-w-3xl flex-col md:h-dvh">
      <div className="flex items-center justify-between px-4 pb-2 pt-4 md:pt-6">
        <h1 className="text-xl font-semibold">Log</h1>
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={newChat}>New conversation</Button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-4" aria-live="polite">
        {loaded && messages.length === 0 && (
          <div className="py-10">
            <p className="font-display text-2xl font-semibold leading-snug">Tell me what you ate, lifted, weighed or drank.</p>
            <p className="mt-2 max-w-prose text-ink-soft">
              Write it the way you&apos;d say it. If something&apos;s missing — how much chicken, which rice — I&apos;ll ask instead of guessing.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}
                  className="rounded-full border border-line bg-surface px-3 py-1.5 text-sm text-ink-soft hover:border-ink-faint hover:text-ink">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        <ol className="space-y-3 pb-4">
          {messages.map((m) => (
            <li key={m.id} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
              {m.role === "user" ? (
                <div className="max-w-[85%] rounded-bubble rounded-br-md bg-ink px-4 py-2.5 text-white">
                  <p className="whitespace-pre-line">{m.content}</p>
                </div>
              ) : (
                <AssistantBubble m={m} />
              )}
            </li>
          ))}
        </ol>
        <div ref={bottom} />
      </div>

      {lastOptions && lastOptions.length > 0 && !sending && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {lastOptions.map((o, i) => (
            <button key={o.id} onClick={() => send(String(i + 1))}
              className="rounded-full border border-protein/30 bg-protein/5 px-3 py-1.5 text-sm text-protein hover:bg-protein/10">
              {o.name}
            </button>
          ))}
        </div>
      )}

      <form
        className="border-t border-line bg-paper px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
      >
        <div className="flex items-end gap-2">
          <label htmlFor="composer" className="sr-only">Message</label>
          <textarea
            id="composer"
            ref={input}
            rows={1}
            value={text}
            maxLength={2000}
            placeholder="e.g. 2 rotis and 150g paneer for dinner"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(text);
              }
            }}
            className="max-h-40 min-h-[44px] flex-1 resize-none rounded-xl border border-line bg-surface px-4 py-2.5 text-[15px] focus:border-protein focus:outline-none"
          />
          <Button type="submit" disabled={sending || !text.trim()} className="h-11">
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}

function AssistantBubble({ m }: { m: Msg }) {
  if (m.pending) {
    return (
      <div className="rounded-bubble rounded-bl-md border border-line bg-surface px-4 py-3 text-ink-faint" role="status">
        Working it out…
      </div>
    );
  }
  const payload = payloadOf(m);
  const totals = (payload.result?.totals ?? null) as { calories: number; protein_g: number; carbs_g: number; fat_g: number } | null;
  const asking = payload.status === "needs_clarification";
  return (
    <div className={cn(
      "max-w-[85%] overflow-hidden rounded-bubble rounded-bl-md border bg-surface",
      m.failed || payload.status === "failed" ? "border-danger/30" : asking ? "border-carbs/50" : "border-line",
    )}>
      <p className={cn("whitespace-pre-line px-4 py-2.5", m.failed && "text-danger")}>{m.content}</p>
      {totals && (
        <div className="border-t border-line bg-paper/60 px-4 py-2.5">
          <MacroBar protein={totals.protein_g} carbs={totals.carbs_g} fat={totals.fat_g} animate />
          <div className="tabular mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink-soft">
            <span><b className="font-semibold text-ink">{num(totals.calories)}</b> kcal</span>
            <span><b className="font-semibold text-protein">{num(totals.protein_g, 1)}</b> g protein</span>
            <span><b className="font-semibold text-carbs">{num(totals.carbs_g, 1)}</b> g carbs</span>
            <span><b className="font-semibold text-fat">{num(totals.fat_g, 1)}</b> g fat</span>
          </div>
        </div>
      )}
      <p className="px-4 pb-2 text-[11px] text-ink-faint">{time(m.created_at)}</p>
    </div>
  );
}
