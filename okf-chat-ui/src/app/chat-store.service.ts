import { Injectable, computed, signal } from '@angular/core';
import { QueryResponse } from './chat.service';

export interface Message {
  role: 'user' | 'bot';
  text?: string;
  error?: boolean;
  /** raw technical detail behind a friendly error message */
  detail?: string;
  result?: QueryResponse;
  showTimings?: boolean;
  copied?: boolean;
}

export interface Chat {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
}

export interface ChatGroup {
  label: string;
  chats: Chat[];
}

interface Settings {
  showSql: boolean;
  sidebarOpen: boolean;
}

const CHATS_KEY = 'okf.chats.v1';
const SETTINGS_KEY = 'okf.settings.v1';
const MAX_CHATS = 30;
const DAY_MS = 86_400_000;

// Browser storage can be unavailable (private mode, quota, blocked): never let it break the app.
function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown): boolean {
  try {
    // `copied` is a transient UI flag, not worth saving
    localStorage.setItem(key, JSON.stringify(value, (k, v) => (k === 'copied' ? undefined : v)));
    return true;
  } catch {
    return false;
  }
}

function isChat(c: unknown): c is Chat {
  const x = c as Chat;
  return !!x && typeof x.id === 'string' && typeof x.title === 'string' && Array.isArray(x.messages);
}

@Injectable({ providedIn: 'root' })
export class ChatStore {
  private readonly saved = readJson<Partial<Settings>>(SETTINGS_KEY, {});

  readonly chats = signal<Chat[]>(this.loadChats());
  /** null = an empty draft; the chat is created when the first question is sent */
  readonly activeId = signal<string | null>(null);
  readonly showSql = signal<boolean>(this.saved.showSql ?? true);
  readonly sidebarOpen = signal<boolean>(this.saved.sidebarOpen ?? (typeof window !== 'undefined' && window.innerWidth > 800));

  readonly active = computed(() => this.chats().find((c) => c.id === this.activeId()) ?? null);
  readonly messages = computed(() => this.active()?.messages ?? []);

  readonly groups = computed<ChatGroup[]>(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const t0 = today.getTime();
    const buckets: ChatGroup[] = [
      { label: 'Today', chats: [] },
      { label: 'Yesterday', chats: [] },
      { label: 'Earlier', chats: [] },
    ];
    for (const c of [...this.chats()].sort((a, b) => b.updatedAt - a.updatedAt)) {
      buckets[c.updatedAt >= t0 ? 0 : c.updatedAt >= t0 - DAY_MS ? 1 : 2].chats.push(c);
    }
    return buckets.filter((b) => b.chats.length);
  });

  newChat() {
    this.activeId.set(null);
  }

  select(id: string) {
    if (this.chats().some((c) => c.id === id)) this.activeId.set(id);
  }

  /** Returns the active chat's id, creating a chat titled after `firstQuestion` if none is active. */
  ensureChat(firstQuestion: string): string {
    const current = this.activeId();
    if (current && this.chats().some((c) => c.id === current)) return current;
    const now = Date.now();
    const chat: Chat = {
      id: `c${now.toString(36)}${Math.random().toString(36).slice(2, 7)}`,
      title: firstQuestion.length > 48 ? `${firstQuestion.slice(0, 47)}…` : firstQuestion,
      createdAt: now,
      updatedAt: now,
      messages: [],
    };
    this.chats.update((l) => [chat, ...l].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, MAX_CHATS));
    this.activeId.set(chat.id);
    this.persistChats();
    return chat.id;
  }

  add(chatId: string, message: Message) {
    this.chats.update((l) =>
      l.map((c) => (c.id === chatId ? { ...c, messages: [...c.messages, message], updatedAt: Date.now() } : c)),
    );
    this.persistChats();
  }

  patch(chatId: string, index: number, changes: Partial<Message>) {
    this.chats.update((l) =>
      l.map((c) =>
        c.id === chatId ? { ...c, messages: c.messages.map((m, i) => (i === index ? { ...m, ...changes } : m)) } : c,
      ),
    );
    this.persistChats();
  }

  remove(id: string) {
    this.chats.update((l) => l.filter((c) => c.id !== id));
    if (this.activeId() === id) this.activeId.set(null);
    this.persistChats();
  }

  clearAll() {
    this.chats.set([]);
    this.activeId.set(null);
    this.persistChats();
  }

  setShowSql(value: boolean) {
    this.showSql.set(value);
    this.persistSettings();
  }

  toggleSidebar() {
    this.sidebarOpen.update((v) => !v);
    this.persistSettings();
  }

  private loadChats(): Chat[] {
    const raw = readJson<unknown>(CHATS_KEY, []);
    return (Array.isArray(raw) ? raw.filter(isChat) : []).slice(0, MAX_CHATS);
  }

  /** Save; if the browser quota is exceeded, drop the least recently used chat and retry. */
  private persistChats() {
    while (!writeJson(CHATS_KEY, this.chats()) && this.chats().length > 1) {
      const oldest = [...this.chats()].sort((a, b) => a.updatedAt - b.updatedAt)[0];
      if (oldest.id === this.activeId()) break;
      this.chats.update((l) => l.filter((c) => c.id !== oldest.id));
    }
  }

  private persistSettings() {
    writeJson(SETTINGS_KEY, { showSql: this.showSql(), sidebarOpen: this.sidebarOpen() } satisfies Settings);
  }
}
