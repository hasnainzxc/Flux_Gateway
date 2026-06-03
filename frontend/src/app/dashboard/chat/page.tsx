"use client"

import { useState, useRef, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import { Send, Bot, User, Loader2 } from "lucide-react"
import { motion, AnimatePresence } from "motion/react"

interface Message {
  role: "user" | "agent"
  content: string
  citations?: Array<{ id: string; document_name: string; page: number; score: number; excerpt: string }>
  tokensUsed?: number
  latencyMs?: number
}

function getScoreColor(score: number) {
  if (score >= 0.9) return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
  if (score >= 0.7) return "bg-amber-500/20 text-amber-400 border-amber-500/30"
  return "bg-red-500/20 text-red-400 border-red-500/30"
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const query = input
    setInput("")
    setLoading(true)
    setMessages((prev) => [...prev, { role: "user", content: query }])

    try {
      const result = await api.query(query)
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: result.answer,
          citations: result.citations as Message["citations"],
          tokensUsed: result.tokens_used,
          latencyMs: result.latency_ms,
        },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: "Sorry, something went wrong. Please try again.",
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Agent Chat</h1>
        <p className="text-sm text-muted-foreground">
          Ask questions about your data. All queries are schema-grounded with citations.
        </p>
      </div>

      <Card className="flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex h-full items-center justify-center text-center text-muted-foreground">
              <p>Ask a question about your connected data to get started.</p>
            </div>
          )}

          <AnimatePresence>
            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
              >
                {msg.role === "agent" && (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}

                <div
                  className={`max-w-[80%] space-y-2 rounded-lg px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/50"
                  }`}
                >
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                  {msg.citations && msg.citations.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-2 border-t border-border">
                      {msg.citations.map((cit, j) => (
                        <Badge
                          key={j}
                          variant="outline"
                          className={`text-xs cursor-pointer ${getScoreColor(cit.score)}`}
                          title={cit.excerpt}
                        >
                          [{j + 1}] {cit.document_name}:{cit.page}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {msg.tokensUsed !== undefined && (
                    <p className="text-xs text-muted-foreground">
                      {msg.tokensUsed} tokens · {msg.latencyMs}ms
                    </p>
                  )}
                </div>

                {msg.role === "user" && (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-secondary">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </motion.div>
            ))}

            {loading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex gap-3"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Thinking...</span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
          <div ref={endRef} />
        </div>

        <div className="border-t border-border p-4">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your data..."
              rows={2}
              className="flex-1 resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              disabled={loading}
            />
            <Button onClick={handleSend} disabled={loading || !input.trim()} size="icon">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
