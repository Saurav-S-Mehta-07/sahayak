import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  clearConversation,
  deleteConversation,
  fetchConversations,
  renameConversation,
  sendQuestion,
} from "../services/api.js";
import { useAuth } from "./AuthContext.jsx";
import { getDisplayLocale } from "../utils/language.js";

const ChatContext = createContext(null);
const STORAGE_KEY = "yojana-sahayak-conversations-v2";
const LANGUAGE_KEY = "yojana-sahayak-ui-language-v1";

function readStorage(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
}

export function ChatProvider({ children }) {
  const { user } = useAuth();
  const [chats, setChats] = useState([]);
  const [loadedFor, setLoadedFor] = useState(null);
  const [historyError, setHistoryError] = useState("");
  const [activeId, setActiveId] = useState(null);
  const [pending, setPending] = useState(false);
  const [language, setLanguage] = useState(() =>
    readStorage(LANGUAGE_KEY, "auto"),
  );
  const activeChat = chats.find((chat) => chat.id === activeId) ?? null;

  useEffect(() => {
    let active = true;
    if (!user) {
      setChats([]);
      setActiveId(null);
      setLoadedFor(null);
      return () => {
        active = false;
      };
    }

    const storageKey = `${STORAGE_KEY}:${user.id}`;
    setChats(readStorage(storageKey, []));
    setLoadedFor(user.id);
    setHistoryError("");
    fetchConversations()
      .then((remoteChats) => {
        if (!active) return;
        const localChats = readStorage(storageKey, []);
        const byId = new Map(remoteChats.map((chat) => [chat.id, chat]));
        for (const localChat of localChats) {
          const remoteChat = byId.get(localChat.id);
          if (!remoteChat || localChat.messages.length >= remoteChat.messages.length) {
            byId.set(localChat.id, localChat);
          } else {
            byId.set(localChat.id, {
              ...remoteChat,
              messages: remoteChat.messages.map((message, index) => ({
                ...message,
                id: `${remoteChat.id}-${index}`,
              })),
            });
          }
        }
        setChats([...byId.values()]);
      })
      .catch((error) => {
        if (active) setHistoryError(error.message);
      });
    return () => {
      active = false;
    };
  }, [user?.id]);

  useEffect(() => {
    if (user && loadedFor === user.id) {
      localStorage.setItem(
        `${STORAGE_KEY}:${user.id}`,
        JSON.stringify(chats),
      );
    }
  }, [chats, loadedFor, user]);

  useEffect(() => {
    localStorage.setItem(LANGUAGE_KEY, JSON.stringify(language));
  }, [language]);

  useEffect(() => {
    document.documentElement.lang = getDisplayLocale(language) || "en";
    document.documentElement.dir = "ltr";
  }, [language]);

  const createChat = useCallback(() => {
    const chat = {
      id: crypto.randomUUID(),
      title: "New conversation",
      updatedAt: new Date().toISOString(),
      messages: [],
    };
    setChats((current) => [chat, ...current]);
    setActiveId(chat.id);
    return chat.id;
  }, []);

  const selectChat = useCallback((id) => {
    setActiveId(id);
  }, []);

  const renameChat = useCallback(async (id, rawTitle) => {
    const title = rawTitle.trim().slice(0, 80);
    if (!title) return { ok: false, error: "Conversation title cannot be empty." };
    const previous = chats.find((chat) => chat.id === id);
    setChats((current) =>
      current.map((chat) => chat.id === id ? { ...chat, title } : chat),
    );
    if (previous?.messages.length) {
      try {
        await renameConversation(id, title);
      } catch (error) {
        setChats((current) =>
          current.map((chat) => chat.id === id ? { ...chat, title: previous.title } : chat),
        );
        return { ok: false, error: error.message };
      }
    }
    return { ok: true };
  }, [chats]);

  const clearChat = useCallback(async (id) => {
    const chat = chats.find((item) => item.id === id);
    if (!chat) return { ok: false, error: "Conversation not found." };
    if (chat.messages.length) {
      try {
        await clearConversation(id);
      } catch (error) {
        return { ok: false, error: error.message };
      }
    }
    setChats((current) =>
      current.map((item) => item.id === id ? { ...item, messages: [] } : item),
    );
    return { ok: true };
  }, [chats]);

  const deleteChat = useCallback(
    (id) => {
      const deleted = chats.find((chat) => chat.id === id);
      setChats((current) => current.filter((chat) => chat.id !== id));
      if (activeId === id) setActiveId(null);
      if (deleted?.messages.length) {
        deleteConversation(id).catch((error) => setHistoryError(error.message));
      }
    },
    [activeId, chats],
  );

  const submit = useCallback(
    async (rawQuery, { retry = false, retryMessageId = null } = {}) => {
      const query = rawQuery.trim();
      if (!query || pending) return;

      const conversationId = activeId || createChat();
      const userMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
        createdAt: new Date().toISOString(),
      };
      if (!retry) {
        setChats((current) =>
          current.map((chat) =>
            chat.id === conversationId
              ? {
                  ...chat,
                  title:
                    chat.messages.length === 0 && chat.title === "New conversation"
                      ? query.slice(0, 52)
                      : chat.title,
                  updatedAt: new Date().toISOString(),
                  messages: [...chat.messages, userMessage],
                }
              : chat,
          ),
        );
      }

      setPending(true);
      try {
        const response = await sendQuestion({
          query,
          conversationId,
          conversationTitle:
            chats.find((chat) => chat.id === conversationId)?.title || query.slice(0, 52),
          responseLanguage: language,
        });
        const assistantMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          language: response.language,
          direction: response.direction,
          createdAt: new Date().toISOString(),
        };
        setChats((current) =>
          current.map((chat) =>
            chat.id === conversationId
              ? {
                  ...chat,
                  updatedAt: new Date().toISOString(),
                  messages: [...chat.messages, assistantMessage],
                }
              : chat,
          ),
        );
        return { ok: true, conversationId };
      } catch (error) {
        if (!retry || retryMessageId) {
          setChats((current) =>
            current.map((chat) =>
              chat.id === conversationId
                ? {
                    ...chat,
                    messages: chat.messages.map((message) =>
                      message.id === (retryMessageId || userMessage.id)
                        ? { ...message, failed: true }
                        : message,
                    ),
                  }
                : chat,
            ),
          );
        }
        return { ok: false, error: error.message, conversationId, query };
      } finally {
        setPending(false);
      }
    },
    [activeId, chats, createChat, language, pending],
  );

  const retryMessage = useCallback(
    (message) => {
      setChats((current) =>
        current.map((chat) =>
          chat.id === activeId
            ? {
                ...chat,
                messages: chat.messages.map((item) =>
                  item.id === message.id ? { ...item, failed: false } : item,
                ),
              }
            : chat,
        ),
      );
      return submit(message.content, { retry: true, retryMessageId: message.id });
    },
    [activeId, submit],
  );

  const regenerate = useCallback(async () => {
    const lastUser = [...(activeChat?.messages ?? [])]
      .reverse()
      .find((message) => message.role === "user");
    if (!lastUser) return null;
    setChats((current) =>
      current.map((chat) =>
        chat.id === activeId
          ? {
              ...chat,
              messages: chat.messages.filter(
                (message) =>
                  message.role !== "assistant" ||
                  new Date(message.createdAt) <= new Date(lastUser.createdAt),
              ),
            }
          : chat,
      ),
    );
    return submit(lastUser.content, { retry: true });
  }, [activeChat, activeId, submit]);

  const value = useMemo(
    () => ({
      chats: [...chats].sort(
        (a, b) => new Date(b.updatedAt) - new Date(a.updatedAt),
      ),
      activeId,
      activeChat,
      pending,
      historyError,
      language,
      setLanguage,
      createChat,
      selectChat,
      deleteChat,
      renameChat,
      clearChat,
      submit,
      retryMessage,
      regenerate,
    }),
    [
      chats,
      activeId,
      activeChat,
      pending,
      historyError,
      language,
      createChat,
      selectChat,
      deleteChat,
      renameChat,
      clearChat,
      submit,
      retryMessage,
      regenerate,
    ],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat() {
  const context = useContext(ChatContext);
  if (!context) throw new Error("useChat must be used within ChatProvider");
  return context;
}
