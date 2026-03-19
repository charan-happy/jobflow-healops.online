const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI(path: string, options: RequestInit = {}) {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}/api${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail || "Request failed");
  }

  return res.json();
}

// Auth
export const register = (data: {
  email: string;
  password: string;
  full_name: string;
}) => fetchAPI("/auth/register", { method: "POST", body: JSON.stringify(data) });

export const login = (data: { email: string; password: string }) =>
  fetchAPI("/auth/login", { method: "POST", body: JSON.stringify(data) });

export const getMe = () => fetchAPI("/auth/me");

// Profile
export const updateProfile = (data: Record<string, unknown>) =>
  fetchAPI("/profile", { method: "PUT", body: JSON.stringify(data) });

export const uploadResume = async (file: File) => {
  const token = localStorage.getItem("token");
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/api/profile/resume`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail);
  }
  return res.json();
};

export const getResumes = () => fetchAPI("/profile/resumes");

// Jobs
export const createJob = (data: Record<string, unknown>) =>
  fetchAPI("/jobs", { method: "POST", body: JSON.stringify(data) });

export const getJobs = (skip = 0, limit = 20) =>
  fetchAPI(`/jobs?skip=${skip}&limit=${limit}`);

export const getJob = (id: number) => fetchAPI(`/jobs/${id}`);

export const matchJobs = (limit = 20) =>
  fetchAPI(`/jobs/match/all?limit=${limit}`);

export const optimizeResume = (jobId: number) =>
  fetchAPI(`/jobs/${jobId}/optimize-resume`, { method: "POST" });

// Applications
export const applyToJob = (jobId: number) =>
  fetchAPI(`/jobs/${jobId}/apply`, { method: "POST" });

export const getApplications = (status?: string) =>
  fetchAPI(`/jobs/applications/all${status ? `?status=${status}` : ""}`);

export const updateApplicationStatus = (appId: number, status: string) =>
  fetchAPI(`/jobs/applications/${appId}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });

// Agent — Auto Discovery
export const triggerDiscovery = () =>
  fetchAPI("/agent/discover", { method: "POST" });

export const getDiscoveryStatus = () =>
  fetchAPI("/agent/discover/status");

export const getInterviewPrep = (jobId: number) =>
  fetchAPI(`/agent/interview-prep/${jobId}`);

// Notifications
export const testNotification = () =>
  fetchAPI("/profile/test-notification", { method: "POST" });

// Cover Letter
export const generateCoverLetter = (jobId: number) =>
  fetchAPI(`/jobs/${jobId}/cover-letter`, { method: "POST" });

// Auto Apply
export const autoApply = (jobId: number) =>
  fetchAPI(`/agent/auto-apply/${jobId}`, { method: "POST" });

export const getAutoApplyStatus = (jobId: number) =>
  fetchAPI(`/agent/auto-apply/${jobId}/status`);

// Application Timeline
export const getApplicationTimeline = (appId: number) =>
  fetchAPI(`/jobs/applications/${appId}/timeline`);

export const addApplicationNote = (appId: number, note: string) =>
  fetchAPI(`/jobs/applications/${appId}/note`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
