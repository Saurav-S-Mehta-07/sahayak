import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 90000,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

let csrfToken = "";

export function setCsrfToken(token) {
  csrfToken = token || "";
}

api.interceptors.request.use((config) => {
  if (csrfToken && !["get", "head", "options"].includes(config.method)) {
    config.headers["X-CSRF-Token"] = csrfToken;
  }
  return config;
});

function messageFromError(error) {
  if (error.code === "ECONNABORTED") {
    return "The request timed out. Please try again.";
  }
  if (!error.response) {
    return "Could not reach the backend. Check that the API server is running.";
  }
  const detail = error.response.data?.detail;
  return typeof detail === "string"
    ? detail
    : `The backend returned an error (${error.response.status}).`;
}

export async function checkHealth() {
  try {
    const { data } = await api.get("/health", { timeout: 8000 });
    return data;
  } catch (error) {
    return { status: "offline", error: messageFromError(error) };
  }
}

export async function sendQuestion({
  query,
  conversationId,
  conversationTitle,
  responseLanguage = "auto",
}) {
  try {
    const { data } = await api.post("/chat", {
      query,
      conversation_id: conversationId,
      conversation_title: conversationTitle,
      response_language: responseLanguage,
    });
    if (
      typeof data?.answer !== "string" ||
      typeof data?.conversation_id !== "string" ||
      !Array.isArray(data?.sources)
    ) {
      throw new Error("The backend returned an invalid chat response.");
    }
    return data;
  } catch (error) {
    if (error.message === "The backend returned an invalid chat response.") {
      throw error;
    }
    throw new Error(messageFromError(error));
  }
}

export async function fetchDocuments() {
  try {
    const { data } = await api.get("/documents");
    if (!Array.isArray(data?.documents)) {
      throw new Error("The backend returned an invalid document list.");
    }
    return data.documents;
  } catch (error) {
    if (error.message === "The backend returned an invalid document list.") {
      throw error;
    }
    throw new Error(messageFromError(error));
  }
}

export async function registerAccount(credentials) {
  try {
    const { data } = await api.post("/auth/register", credentials);
    setCsrfToken(data.csrf_token);
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function loginAccount(credentials) {
  try {
    const { data } = await api.post("/auth/login", credentials);
    setCsrfToken(data.csrf_token);
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function fetchCurrentUser() {
  try {
    const { data } = await api.get("/auth/me");
    setCsrfToken(data.csrf_token);
    return data.user;
  } catch (error) {
    setCsrfToken("");
    if (error.response?.status === 401) return null;
    throw new Error(messageFromError(error));
  }
}

export async function logoutAccount() {
  try {
    await api.post("/auth/logout");
    setCsrfToken("");
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function fetchSchemes() {
  try {
    const { data } = await api.get("/schemes");
    return data.schemes;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function recommendSchemes(answers) {
  try {
    const { data } = await api.post("/eligibility/recommendations", { answers });
    if (!Array.isArray(data?.recommendations)) {
      throw new Error("The backend returned an invalid recommendation response.");
    }
    return data;
  } catch (error) {
    if (error.message === "The backend returned an invalid recommendation response.") {
      throw error;
    }
    throw new Error(messageFromError(error));
  }
}

export async function evaluateEligibility(schemeId, answers) {
  try {
    const { data } = await api.post("/eligibility/evaluate", {
      scheme_id: schemeId,
      answers,
    });
    if (typeof data?.status !== "string" || !Array.isArray(data?.criteria)) {
      throw new Error("The backend returned an invalid eligibility response.");
    }
    return data;
  } catch (error) {
    if (error.message === "The backend returned an invalid eligibility response.") {
      throw error;
    }
    throw new Error(messageFromError(error));
  }
}

export async function fetchConversations() {
  try {
    const { data } = await api.get("/conversations");
    return data.conversations;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function deleteConversation(conversationId) {
  try {
    await api.delete(`/conversations/${encodeURIComponent(conversationId)}`);
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function clearConversation(conversationId) {
  try {
    await api.delete(`/conversations/${encodeURIComponent(conversationId)}/messages`);
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function renameConversation(conversationId, title) {
  try {
    const { data } = await api.patch(
      `/conversations/${encodeURIComponent(conversationId)}`,
      { title },
    );
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function fetchAdminDocuments() {
  try {
    const { data } = await api.get("/admin/documents");
    return data.documents;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function fetchAdminDiscoveries() {
  try {
    const { data } = await api.get("/admin/schemes/discovered");
    if (!Array.isArray(data?.discoveries)) {
      throw new Error("The backend returned an invalid discovery list.");
    }
    return data.discoveries;
  } catch (error) {
    if (error.message === "The backend returned an invalid discovery list.") {
      throw error;
    }
    throw new Error(messageFromError(error));
  }
}

export async function discoverAdminSchemes() {
  try {
    const { data } = await api.post("/admin/schemes/discover");
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function reviewAdminDiscovery(discoveryId, status, reviewNotes) {
  try {
    const { data } = await api.patch(
      `/admin/schemes/discovered/${discoveryId}`,
      { status, review_notes: reviewNotes },
    );
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function fetchAdminEligibilityCriteria(schemeId) {
  try {
    const { data } = await api.get(
      `/admin/schemes/${encodeURIComponent(schemeId)}/eligibility-criteria`,
    );
    return data.criteria;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function createAdminEligibilityCriterion(schemeId, criterion) {
  try {
    const { data } = await api.post(
      `/admin/schemes/${encodeURIComponent(schemeId)}/eligibility-criteria`,
      criterion,
    );
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function updateAdminScheme(schemeId, changes) {
  try {
    const { data } = await api.patch(`/admin/schemes/${schemeId}`, changes);
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function verifyAdminSchemeSource(schemeId) {
  try {
    const { data } = await api.post(`/admin/schemes/${schemeId}/verify-source`);
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function uploadAdminDocument(formData) {
  try {
    const { data } = await api.post("/admin/documents", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function verifyAdminDocument(documentId) {
  try {
    const { data } = await api.post(`/admin/documents/${documentId}/verify`);
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function ingestAdminDocument(documentId) {
  try {
    const { data } = await api.post(`/admin/documents/${documentId}/ingest`);
    return data;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}

export async function fetchDocumentEvents(documentId) {
  try {
    const { data } = await api.get(`/admin/documents/${documentId}/events`);
    return data.events;
  } catch (error) {
    throw new Error(messageFromError(error));
  }
}
