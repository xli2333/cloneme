import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  ChatResponse,
  ConversationMeta,
  ConversationResponse,
  FeedbackResponse,
  MessageDTO,
  SearchResponse,
  SearchResultDTO,
} from './types'
import dAvatar from '../pic/D.jpg'
import dxaAvatar from '../pic/dxa.jpg'

const STORAGE_LIST = 'doppel_front_conversations'
const STORAGE_ACTIVE = 'doppel_front_active_id'

type UiMessage = {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
  temp?: boolean
}

type ContextMenuState = {
  open: boolean
  x: number
  y: number
  messageId: number | null
}

type HealthLite = {
  status: string
  env: string
  model_pro: string
  model_flash: string
}

type PendingUserMessage = {
  tempId: number
  text: string
  createdAt: string
}

type PendingBatch = {
  conversationId: string
  startedAt: number
  items: PendingUserMessage[]
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') || ''
const VITE_PASSWORD = (import.meta.env.VITE_PASSWORD as string | undefined)?.trim() || ''
const INPUT_IDLE_BASE_MS = 2800
const INPUT_IDLE_MAX_MS = 3400
const INPUT_BATCH_MAX_WAIT_MS = 7000
const INPUT_BATCH_MAX_ITEMS = 6
const RETRY_FLUSH_WHILE_SENDING_MS = 220

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path
}

function createConversationId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function short(text: string, n = 16): string {
  const t = text.replace(/\s+/g, ' ').trim()
  if (!t) return 'EMPTY LOG'
  return t.length <= n ? t : `${t.slice(0, n)}...`
}

function nowIso(): string {
  return new Date().toISOString()
}

function readConversations(): ConversationMeta[] {
  try {
    const raw = localStorage.getItem(STORAGE_LIST)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .map((x) => ({
        id: String(x.id || ''),
        title: String(x.title || 'NEW ROOM'),
        preview: String(x.preview || ''),
        updatedAt: Number(x.updatedAt || Date.now()),
      }))
      .filter((x) => x.id)
      .sort((a, b) => b.updatedAt - a.updatedAt)
  } catch {
    return []
  }
}

function saveConversations(list: ConversationMeta[], activeId: string): void {
  localStorage.setItem(STORAGE_LIST, JSON.stringify(list))
  localStorage.setItem(STORAGE_ACTIVE, activeId)
}

function formatClock(isoOrTs: string | number): string {
  const d = typeof isoOrTs === 'number' ? new Date(isoOrTs) : new Date(isoOrTs)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return sessionStorage.getItem('doppel_auth') === 'true'
  })
  const [passwordInput, setPasswordInput] = useState('')
  const [passwordError, setPasswordError] = useState(false)

  const [conversations, setConversations] = useState<ConversationMeta[]>([])
  const [activeId, setActiveId] = useState<string>('')
  const [messages, setMessages] = useState<UiMessage[]>([])
  const [input, setInput] = useState('')
  const [status, setStatus] = useState('ONLINE')
  const [sending, setSending] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [feedbackComment, setFeedbackComment] = useState('')
  const [backendInfo, setBackendInfo] = useState<HealthLite | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResultDTO[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [highlightedMessageId, setHighlightedMessageId] = useState<number | null>(null)
  const [ctxMenu, setCtxMenu] = useState<ContextMenuState>({
    open: false,
    x: 0,
    y: 0,
    messageId: null,
  })

  const chatPaneRef = useRef<HTMLDivElement | null>(null)
  const activeIdRef = useRef<string>('')
  const targetMessageIdRef = useRef<number | null>(null)
  const searchTimeoutRef = useRef<number | null>(null)
  const sendingRef = useRef<boolean>(false)
  const pendingBatchRef = useRef<PendingBatch | null>(null)
  const pendingFlushTimerRef = useRef<number | null>(null)
  const tempIdSeqRef = useRef<number>(0)

  const activeConv = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null,
    [conversations, activeId],
  )

  useEffect(() => {
    activeIdRef.current = activeId
  }, [activeId])

  useEffect(() => {
    sendingRef.current = sending
  }, [sending])

  useEffect(() => {
    let list = readConversations()
    if (!list.length) {
      const id = createConversationId()
      list = [{ id, title: 'NEW ROOM', preview: '', updatedAt: Date.now() }]
    }

    const savedActive = localStorage.getItem(STORAGE_ACTIVE)
    let resolvedActive = savedActive && list.some((c) => c.id === savedActive) ? savedActive : list[0].id

    // Mobile: start in list view by default
    if (window.innerWidth <= 768) {
      resolvedActive = ''
    }

    setConversations(list)
    setActiveId(resolvedActive)
    saveConversations(list, resolvedActive)
  }, [])

  useEffect(() => {
    if (!activeId) return
    setSelectedIds(new Set())
    setFeedbackComment('')
    void loadConversation(activeId)
  }, [activeId])

  useEffect(() => {
    if (!chatPaneRef.current) return
    chatPaneRef.current.scrollTop = chatPaneRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    const handlePointerDown = (e: PointerEvent) => {
      const target = e.target as Node
      if (ctxMenu.open) {
        const menu = document.getElementById('ctxMenuCard')
        if (menu && !menu.contains(target)) {
          setCtxMenu((prev) => ({ ...prev, open: false }))
        }
      }
    }
    window.addEventListener('pointerdown', handlePointerDown)
    return () => window.removeEventListener('pointerdown', handlePointerDown)
  }, [ctxMenu.open])

  useEffect(() => {
    async function loadHealth(): Promise<void> {
      try {
        const res = await fetch(apiUrl('/api/health'))
        if (!res.ok) return
        const data = (await res.json()) as HealthLite
        setBackendInfo(data)
      } catch {
        setBackendInfo(null)
      }
    }
    void loadHealth()
  }, [])

  useEffect(() => {
    return () => {
      if (pendingFlushTimerRef.current !== null) {
        window.clearTimeout(pendingFlushTimerRef.current)
      }
    }
  }, [])

  function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!VITE_PASSWORD) {
      setPasswordError(true)
      return
    }
    if (passwordInput === VITE_PASSWORD) {
      setIsAuthenticated(true)
      sessionStorage.setItem('doppel_auth', 'true')
      setPasswordError(false)
    } else {
      setPasswordError(true)
    }
  }

  function touchConversation(conversationId: string, text: string, role: 'user' | 'assistant'): void {
    setConversations((prev) => {
      const next = [...prev]
      const idx = next.findIndex((x) => x.id === conversationId)
      if (idx < 0) return prev
      const curr = next[idx]
      const title =
        role === 'user' && (curr.title === 'NEW ROOM' || curr.title.startsWith('ROOM'))
          ? short(text, 12).toUpperCase()
          : curr.title
      next[idx] = {
        ...curr,
        title,
        preview: text,
        updatedAt: Date.now(),
      }
      next.sort((a, b) => b.updatedAt - a.updatedAt)
      saveConversations(next, activeIdRef.current || conversationId)
      return next
    })
  }

  async function loadConversation(conversationId: string, jumpToId?: number): Promise<void> {
    try {
      const res = await fetch(apiUrl(`/api/conversation/${conversationId}`))
      if (!res.ok) return
      const data = (await res.json()) as ConversationResponse
      if (activeIdRef.current !== conversationId) return

      setMessages(
        data.messages.map((m: MessageDTO) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at,
        })),
      )

      if (jumpToId) {
        targetMessageIdRef.current = jumpToId
      }

      const last = data.messages[data.messages.length - 1]
      if (last) {
        touchConversation(conversationId, last.content, last.role)
      }
    } catch {
      // noop
    }
  }

  useEffect(() => {
    if (!chatPaneRef.current || messages.length === 0 || !targetMessageIdRef.current) return
    const tid = targetMessageIdRef.current
    
    // We need a small delay for the DOM to update
    window.setTimeout(() => {
      const el = document.getElementById(`msg-${tid}`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        setHighlightedMessageId(tid)
        window.setTimeout(() => setHighlightedMessageId(null), 3000)
        targetMessageIdRef.current = null
      }
    }, 100)
  }, [messages])

  async function performSearch(q: string): Promise<void> {
    if (searchTimeoutRef.current) window.clearTimeout(searchTimeoutRef.current)
    
    if (!q.trim()) {
      setIsSearching(false)
      setSearchResults([])
      return
    }

    searchTimeoutRef.current = window.setTimeout(async () => {
      try {
        const res = await fetch(apiUrl(`/api/search?q=${encodeURIComponent(q)}`))
        if (!res.ok) {
          console.error('Search failed:', res.statusText)
          return
        }
        const data = (await res.json()) as SearchResponse
        setSearchResults(data.results)
      } catch (err) {
        console.error('Search error:', err)
        setSearchResults([])
      }
    }, 300)
  }

  function jumpToSearchResult(res: SearchResultDTO): void {
    if (res.conversation_id === activeId) {
      const el = document.getElementById(`msg-${res.id}`)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        setHighlightedMessageId(res.id)
        window.setTimeout(() => setHighlightedMessageId(null), 3000)
      }
    } else {
      activeIdRef.current = res.conversation_id
      setActiveId(res.conversation_id)
      void loadConversation(res.conversation_id, res.id)
    }
  }

  function createRoom(): void {
    void flushPendingBatch()
    const id = createConversationId()
    setConversations((prev) => {
      const roomNumber = prev.length + 1
      const next = [{ id, title: `ROOM ${roomNumber}`, preview: '', updatedAt: Date.now() }, ...prev]
      saveConversations(next, id)
      return next
    })
    setActiveId(id)
    setMessages([])
    setSelectedIds(new Set())
    setFeedbackComment('')
  }

  function switchRoom(id: string): void {
    if (id === activeId) return
    void flushPendingBatch()
    setActiveId(id)
    saveConversations(conversations, id)
  }

  function deleteRoom(id: string, e: React.MouseEvent): void {
    e.stopPropagation()
    if (!window.confirm('确定要删除这个聊天吗？')) return

    discardPendingBatchForConversation(id)
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id)
      let nextActive = activeId
      if (id === activeId) {
        nextActive = next.length > 0 ? next[0].id : ''
      }
      if (next.length === 0) {
        const newId = createConversationId()
        const initialRoom = { id: newId, title: 'NEW ROOM', preview: '', updatedAt: Date.now() }
        next.push(initialRoom)
        nextActive = newId
      }
      setActiveId(nextActive)
      saveConversations(next, nextActive)
      return next
    })
  }

  function openContextMenu(evt: React.MouseEvent, messageId: number): void {
    evt.preventDefault()
    evt.stopPropagation()
    const x = Math.min(evt.clientX, window.innerWidth - 260)
    const y = Math.min(evt.clientY, window.innerHeight - 240)
    setCtxMenu({ open: true, x, y, messageId })
  }

  function toggleSelected(id: number): void {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function clearSelected(): void {
    setSelectedIds(new Set())
  }

  async function submitFeedback(ids: number[], comment = ''): Promise<void> {
    if (!activeId || !ids.length) return
    try {
      const res = await fetch(apiUrl('/api/feedback'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: activeId,
          message_ids: ids,
          comment,
        }),
      })
      const data = (await res.json()) as FeedbackResponse | { detail?: string }
      if (!res.ok) {
        alert((data as { detail?: string }).detail || 'Feedback submit failed')
        return
      }
      const ok = data as FeedbackResponse
      alert(`Accepted ${ok.accepted_count} items, preference version v${ok.preference_version}\n${ok.summary}`)
      setSelectedIds(new Set())
      setFeedbackComment('')
      await loadConversation(activeId)
    } catch {
      alert('Feedback submit error')
    }
  }

  async function sendMessage(): Promise<void> {
    const text = input.trim()
    const conversationId = activeId
    if (!text || !conversationId) return

    setInput('')
    const createdAt = nowIso()
    tempIdSeqRef.current += 1
    const tempId = -(Date.now() * 100 + tempIdSeqRef.current)
    const pendingItem: PendingUserMessage = {
      tempId,
      text,
      createdAt,
    }

    setMessages((prev) => [
      ...prev,
      {
        id: tempId,
        role: 'user',
        content: text,
        created_at: createdAt,
        temp: true,
      },
    ])
    touchConversation(conversationId, text, 'user')

    const existing = pendingBatchRef.current
    if (!existing || existing.conversationId !== conversationId) {
      if (existing && existing.items.length) {
        void flushPendingBatch()
      }
      pendingBatchRef.current = {
        conversationId,
        startedAt: Date.now(),
        items: [pendingItem],
      }
    } else {
      existing.items.push(pendingItem)
    }

    if (!sendingRef.current) {
      setStatus('发送中...')
    }
    schedulePendingFlush(text)
  }

  function clearPendingFlushTimer(): void {
    if (pendingFlushTimerRef.current === null) return
    window.clearTimeout(pendingFlushTimerRef.current)
    pendingFlushTimerRef.current = null
  }

  function resolveIdleDelayMs(latestText: string, itemCount: number): number {
    let idleMs = INPUT_IDLE_BASE_MS
    if (latestText.length <= 6) idleMs += 250
    if (!/[\u3002\uFF01\uFF1F!?~\uFF5E]$/.test(latestText)) idleMs += 250
    if (itemCount >= 4) idleMs -= 350
    if (itemCount >= 5) idleMs -= 250
    return Math.min(INPUT_IDLE_MAX_MS, Math.max(2200, idleMs))
  }

  function schedulePendingFlush(latestText: string): void {
    const batch = pendingBatchRef.current
    if (!batch || !batch.items.length) return

    if (batch.items.length >= INPUT_BATCH_MAX_ITEMS) {
      void flushPendingBatch()
      return
    }

    const elapsed = Date.now() - batch.startedAt
    const remainMaxWait = INPUT_BATCH_MAX_WAIT_MS - elapsed
    if (remainMaxWait <= 0) {
      void flushPendingBatch()
      return
    }

    const waitMs = Math.min(resolveIdleDelayMs(latestText, batch.items.length), remainMaxWait)
    clearPendingFlushTimer()
    pendingFlushTimerRef.current = window.setTimeout(() => {
      pendingFlushTimerRef.current = null
      void flushPendingBatch()
    }, waitMs)
  }

  function discardPendingBatchForConversation(conversationId: string): void {
    const batch = pendingBatchRef.current
    if (!batch || batch.conversationId !== conversationId) return
    clearPendingFlushTimer()
    pendingBatchRef.current = null
    const removeIds = new Set(batch.items.map((item) => item.tempId))
    setMessages((prev) => prev.filter((m) => !removeIds.has(m.id)))
    if (!sendingRef.current) {
      setStatus('ONLINE')
    }
  }

  function settleStatusAfterSend(): void {
    if (pendingBatchRef.current?.items.length) {
      setStatus('发送中...')
      const latest = pendingBatchRef.current.items[pendingBatchRef.current.items.length - 1]
      schedulePendingFlush(latest.text)
      return
    }
    setStatus('ONLINE')
  }

  function replaceTempBatchWithPersisted(
    batch: PendingBatch,
    userMessageId: number,
  ): void {
    const firstTempId = batch.items[0]?.tempId ?? null
    const tempIds = new Set(batch.items.map((item) => item.tempId))
    setMessages((prev) => {
      return prev.map((m) => {
        if (!tempIds.has(m.id)) return m
        if (m.id === firstTempId) {
          return {
            ...m,
            id: userMessageId,
            temp: false,
          }
        }
        return {
          ...m,
          temp: false,
        }
      })
    })
  }

  async function flushPendingBatch(): Promise<void> {
    const batch = pendingBatchRef.current
    if (!batch || !batch.items.length) return

    if (sendingRef.current) {
      clearPendingFlushTimer()
      pendingFlushTimerRef.current = window.setTimeout(() => {
        pendingFlushTimerRef.current = null
        void flushPendingBatch()
      }, RETRY_FLUSH_WHILE_SENDING_MS)
      return
    }

    clearPendingFlushTimer()
    pendingBatchRef.current = null

    const mergedText = batch.items.map((item) => item.text).join('\n')

    setSending(true)
    setStatus('对方正在输入中...')

    try {
      const res = await fetch(apiUrl('/api/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: batch.conversationId,
          message: mergedText,
        }),
      })
      const data = (await res.json()) as ChatResponse | { detail?: string }
      if (!res.ok) {
        alert((data as { detail?: string }).detail || 'Send failed')
        const removeIds = new Set(batch.items.map((item) => item.tempId))
        setMessages((prev) => prev.filter((m) => !removeIds.has(m.id)))
        setSending(false)
        settleStatusAfterSend()
        return
      }

      const chat = data as ChatResponse
      replaceTempBatchWithPersisted(batch, chat.user_message_id)

      chat.bubbles.forEach((bubble, i) => {
        const delay = Math.max(0, Number(bubble.delay_ms || 0))
        const msgId = Number(chat.assistant_message_ids[i] || i + 1)
        window.setTimeout(() => {
          touchConversation(batch.conversationId, bubble.text, 'assistant')
          if (activeIdRef.current !== batch.conversationId) return
          setMessages((prev) => {
            if (prev.some((m) => m.id === msgId && m.content === bubble.text)) return prev
            return [
              ...prev,
              {
                id: msgId,
                role: 'assistant',
                content: bubble.text,
                created_at: nowIso(),
              },
            ]
          })
        }, delay)
      })

      const maxDelay = chat.bubbles.length
        ? Math.max(...chat.bubbles.map((b) => Number(b.delay_ms || 0)))
        : 0
      window.setTimeout(() => {
        setSending(false)
        settleStatusAfterSend()
      }, maxDelay + 120)
    } catch {
      alert('Send request error')
      const removeIds = new Set(batch.items.map((item) => item.tempId))
      setMessages((prev) => prev.filter((m) => !removeIds.has(m.id)))
      setSending(false)
      settleStatusAfterSend()
    }
  }

  function toggleFromContext(): void {
    const currentId = ctxMenu.messageId
    if (!currentId) return
    toggleSelected(currentId)
    setCtxMenu((prev) => ({ ...prev, open: false }))
  }

  async function markSelectedFromContext(): Promise<void> {
    const currentId = ctxMenu.messageId
    if (!currentId) return
    const next = new Set(selectedIds)
    if (!next.has(currentId)) next.add(currentId)
    setSelectedIds(next)
    setCtxMenu((prev) => ({ ...prev, open: false }))
    await submitFeedback([...next], feedbackComment.trim())
  }

  async function markSingleFromContext(): Promise<void> {
    if (!ctxMenu.messageId) return
    const id = ctxMenu.messageId
    setCtxMenu((prev) => ({ ...prev, open: false }))
    await submitFeedback([id], '')
  }

  if (!isAuthenticated) {
    return (
      <div className="password-gate">
        <form className="password-form" onSubmit={handleLogin}>
          <div className="password-avatar">
            <img src={dxaAvatar} alt="avatar" />
          </div>
          <div className="password-title">dxa</div>
          <div className="password-input-group">
            <input
              type="password"
              placeholder="请输入密码"
              value={passwordInput}
              onChange={(e) => setPasswordInput(e.target.value)}
              autoFocus
            />
            {passwordError && <div className="password-error">密码错误，请重试</div>}
          </div>
          <button type="submit" className="btn-login">登录</button>
        </form>
      </div>
    )
  }

  return (
    <div className="page">
      <div className={`grid-shell ${activeId ? 'in-chat' : 'in-list'}`}>
        <aside className="nav-sidebar desktop-only">
          <div className="nav-avatar">
            <img src={dxaAvatar} alt="me" />
          </div>
          <div className="nav-icon active">🗨️</div>
          <div style={{ marginTop: 'auto' }} className="nav-icon">⚙️</div>
        </aside>

        <aside className="left-rail">
          {/* Mobile Header */}
          <header className="mobile-header mobile-only">
            <div className="mobile-header-title">微信</div>
            <div className="mobile-header-actions">
              <span className="mobile-icon" onClick={() => setIsSearching(!isSearching)}>🔍</span>
              <span className="mobile-icon" onClick={createRoom}>+</span>
            </div>
          </header>

          <section className="rooms-block">
            <div className="rooms-head desktop-only">
              <div className="search-wrapper">
                <input 
                  className="search-input"
                  placeholder="搜索"
                  value={searchQuery}
                  onChange={(e) => {
                    const val = e.target.value
                    setSearchQuery(val)
                    if (!val.trim()) {
                      setIsSearching(false)
                      setSearchResults([])
                    } else {
                      setIsSearching(true)
                      void performSearch(val)
                    }
                  }}
                />
                {searchQuery && (
                  <button className="search-clear" onClick={() => {
                    setSearchQuery('')
                    setIsSearching(false)
                    setSearchResults([])
                  }}>×</button>
                )}
              </div>
              <button type="button" className="btn-ghost" onClick={createRoom} style={{ padding: '2px 8px', fontSize: '16px' }}>
                +
              </button>
            </div>

            <div className="rooms-list">
              {isSearching ? (
                <div className="search-results">
                  <div className="search-res-header">
                    <span>聊天记录</span>
                  </div>
                  {searchResults.length === 0 ? (
                    <div className="search-empty">无结果</div>
                  ) : (
                    searchResults.map((res) => (
                      <button key={`${res.id}`} className="search-res-item" onClick={() => jumpToSearchResult(res)}>
                        <div className="res-title">
                          {conversations.find(c => c.id === res.conversation_id)?.title || '未知聊天'}
                        </div>
                        <div className="res-content">{res.content}</div>
                        <div className="res-time">{formatClock(res.created_at)}</div>
                      </button>
                    ))
                  )}
                </div>
              ) : (
                conversations.map((conv) => (
                  <div key={conv.id} className="room-item-wrapper">
                    <button
                      type="button"
                      className={`room-item ${conv.id === activeId ? 'active' : ''}`}
                      onClick={() => switchRoom(conv.id)}
                    >
                      <div className="room-item-avatar">
                        <img 
                          src={dAvatar} 
                          alt="avatar" 
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://via.placeholder.com/40'
                          }}
                        />
                      </div>
                      <div className="room-item-info">
                        <div className="room-item-top">
                          <div className="room-name">{conv.title}</div>
                          <div className="room-time">{formatClock(conv.updatedAt)}</div>
                        </div>
                        <div className="room-preview">{short(conv.preview || '', 18)}</div>
                      </div>
                    </button>
                    <button 
                      type="button" 
                      className="room-delete-btn"
                      onClick={(e) => deleteRoom(conv.id, e)}
                      title="删除"
                    >
                      ×
                    </button>
                  </div>
                ))
              )}
            </div>
          </section>

          {/* Mobile Bottom Tab Bar */}
          <footer className="mobile-tab-bar mobile-only">
            <div className="tab-item active">
              <div className="tab-icon">🗨️</div>
              <div className="tab-label">微信</div>
            </div>
            <div className="tab-item">
              <div className="tab-icon">👤</div>
              <div className="tab-label">通讯录</div>
            </div>
            <div className="tab-item">
              <div className="tab-icon">🧭</div>
              <div className="tab-label">发现</div>
            </div>
            <div className="tab-item">
              <div className="tab-icon">😎</div>
              <div className="tab-label">我</div>
            </div>
          </footer>
        </aside>

        <section className="chat-stage">
          <header className="stage-topbar">
            {/* Mobile Back Button */}
            <button 
              className="mobile-back-btn mobile-only"
              onClick={() => setActiveId('')}
            >
              &lt;
            </button>
            
            <div className="topbar-room">{activeConv?.title || '微信'}</div>
            
            <div className="mobile-more-btn mobile-only">···</div>

            <div className="topbar-status desktop-only">
              {status === 'ONLINE' ? '' : status}
              {backendInfo?.status === 'ok' ? '' : ' [OFFLINE]'}
            </div>
          </header>

          <div ref={chatPaneRef} className="chat-pane" onScroll={() => setCtxMenu((p) => ({ ...p, open: false }))}>
            {messages.map((msg) => {
              const selected = msg.role === 'assistant' && selectedIds.has(msg.id)
              const highlighted = highlightedMessageId === msg.id
              return (
                <div key={`${msg.id}-${msg.created_at}`} id={`msg-${msg.id}`} className={`msg-row ${msg.role}`}>
                  <div className="avatar">
                    <img 
                      src={msg.role === 'assistant' ? dAvatar : dxaAvatar} 
                      alt="avatar" 
                      onError={(e) => {
                        (e.target as HTMLImageElement).src = 'https://via.placeholder.com/40'
                      }}
                    />
                  </div>
                  <div
                    className={`bubble ${selected ? 'selected' : ''} ${highlighted ? 'highlight' : ''}`}
                    onContextMenu={
                      msg.role === 'assistant' && msg.id > 0
                        ? (e) => openContextMenu(e, msg.id)
                        : undefined
                    }
                  >
                    {msg.content}
                  </div>
                </div>
              )
            })}
          </div>

          <section className={`feedback-panel ${selectedIds.size ? '' : 'hidden'}`}>
            <div className="feedback-count">已选 {selectedIds.size}</div>
            <input
              value={feedbackComment}
              onChange={(e) => setFeedbackComment(e.target.value)}
              className="feedback-input"
              placeholder="反馈备注..."
              maxLength={120}
            />
            <button type="button" className="btn-ghost" onClick={clearSelected}>
              取消
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => void submitFeedback([...selectedIds], feedbackComment.trim())}
            >
              标记为好回答
            </button>
          </section>

          <footer className="composer">
            <div className="composer-mobile-row mobile-only">
              <div className="composer-input-wrapper">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder=""
                  rows={1}
                  className="composer-textarea-mobile"
                />
              </div>
              <span className="toolbar-icon">☺</span>
              {input.length > 0 ? (
                <button type="button" className="btn-send-mobile" onClick={() => void sendMessage()}>发送</button>
              ) : (
                <span className="toolbar-icon">+</span>
              )}
            </div>
            
            <div className="composer-desktop-view desktop-only">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder=""
                rows={3}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void sendMessage()
                  }
                }}
              />
              <div className="composer-actions">
                <button type="button" className="btn-send" onClick={() => void sendMessage()} disabled={!input.trim() || !activeId}>
                  发送(S)
                </button>
              </div>
            </div>
          </footer>
        </section>
      </div>

      {ctxMenu.open ? (
        <div
          id="ctxMenuCard"
          className="ctx-menu"
          style={{ left: ctxMenu.x, top: ctxMenu.y }}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <button type="button" onClick={toggleFromContext}>
            {ctxMenu.messageId && selectedIds.has(ctxMenu.messageId)
              ? '取消选中'
              : '多选'}
          </button>
          <button type="button" onClick={() => void markSelectedFromContext()}>
            标记选中项为好回答
          </button>
          <button type="button" onClick={() => void markSingleFromContext()}>
            仅标记此项为好回答
          </button>
        </div>
      ) : null}
    </div>
  )
}
