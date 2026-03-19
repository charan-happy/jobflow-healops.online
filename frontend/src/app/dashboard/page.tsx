"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  getMe,
  getApplications,
  getJobs,
  triggerDiscovery,
  getDiscoveryStatus,
} from "@/lib/api";

interface Job {
  id: number;
  title: string;
  company: string;
  location: string | null;
  source: string;
}

interface Application {
  id: number;
  job: Job;
  status: string;
  match_score: number | null;
  applied_at: string | null;
  platform: string | null;
}

interface User {
  full_name: string;
  email: string;
  target_roles: string[];
  preferred_locations: string[];
  target_portals: string[];
}

interface DiscoveryRun {
  id: number;
  status: string;
  jobs_found: number;
  started_at: string;
  completed_at: string | null;
}

const SOURCE_COLORS: Record<string, string> = {
  linkedin: "#0a66c2", naukri: "#4a90d9", indeed: "#2164f3",
  wellfound: "#d64045", arc: "#6c5ce7", torre: "#00b894",
  getonboard: "#e17055", google_jobs: "#34a853",
  manual: "#636e72",
};

const SOURCE_LABELS: Record<string, string> = {
  linkedin: "LinkedIn", naukri: "Naukri", indeed: "Indeed",
  wellfound: "Wellfound", arc: "Arc", torre: "Torre",
  getonboard: "GetOnBoard", google_jobs: "Google",
  manual: "Manual",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "#f59e0b", applied: "#3b82f6", interview: "#8b5cf6",
  offer: "#10b981", rejected: "#ef4444", withdrawn: "#6b7280",
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [runs, setRuns] = useState<DiscoveryRun[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [discoverMsg, setDiscoverMsg] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [u, apps, j, r] = await Promise.all([
        getMe(),
        getApplications(),
        getJobs(0, 100),
        getDiscoveryStatus().catch(() => []),
      ]);
      setUser(u);
      setApplications(apps);
      setJobs(j);
      setRuns(r);
      return r as DiscoveryRun[];
    } catch {
      router.push("/login");
      return [];
    }
  }, [router]);

  // Poll discovery status while a run is in progress
  const startPolling = useCallback(() => {
    if (pollRef.current) return; // already polling
    pollRef.current = setInterval(async () => {
      try {
        const [j, r] = await Promise.all([
          getJobs(0, 100),
          getDiscoveryStatus().catch(() => []),
        ]);
        setJobs(j);
        setRuns(r);

        const hasRunning = (r as DiscoveryRun[]).some(
          (run) => run.status === "running"
        );
        if (!hasRunning && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setDiscovering(false);
          setDiscoverMsg((prev) =>
            prev && !prev.startsWith("Error")
              ? "Discovery completed! Jobs list updated."
              : prev
          );
        }
      } catch {
        // ignore polling errors
      }
    }, 10000);
  }, []);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    loadData().then((runs) => {
      // Resume polling if there's already a running discovery
      const hasRunning = (runs as DiscoveryRun[]).some(
        (run) => run.status === "running"
      );
      if (hasRunning) {
        setDiscovering(true);
        setDiscoverMsg("Discovery is running...");
        startPolling();
      }
    });
  }, [loadData, startPolling]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleDiscover = async () => {
    setDiscovering(true);
    setDiscoverMsg("");
    try {
      const result = await triggerDiscovery();
      setDiscoverMsg(
        `Discovery started! Searching ${result.portals.join(", ")} for: ${result.message}`
      );
      startPolling();
    } catch (err) {
      setDiscoverMsg(
        `Error: ${err instanceof Error ? err.message : "Failed to start discovery"}`
      );
      setDiscovering(false);
    }
  };

  const profileComplete =
    user?.target_roles?.length && user?.preferred_locations?.length;

  if (!user)
    return (
      <div className="loading-page">
        <span className="spinner" /> Loading dashboard...
      </div>
    );

  return (
    <>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-brand">
          <span>Job</span>Flow
        </div>
        <div className="navbar-links">
          <a href="/dashboard" className="active">Dashboard</a>
          <a href="/jobs">Jobs</a>
          <a href="/profile">Profile</a>
          <span className="navbar-user">{user.full_name}</span>
          <button
            onClick={() => {
              localStorage.removeItem("token");
              router.push("/login");
            }}
            className="btn btn-ghost btn-sm"
          >
            Logout
          </button>
        </div>
      </nav>

      <div className="page">
        {/* Stats */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <div />
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="btn btn-ghost btn-sm"
            style={{ fontSize: 13 }}
          >
            {refreshing ? <><span className="spinner" /> Refreshing...</> : "Refresh"}
          </button>
        </div>
        <div className="stats-grid">
          {[
            { label: "Jobs Found", value: jobs.length, color: "blue" },
            {
              label: "Applied",
              value: applications.filter((a) => a.status === "applied").length,
              color: "green",
            },
            {
              label: "Interviews",
              value: applications.filter((a) => a.status === "interview").length,
              color: "purple",
            },
            {
              label: "Offers",
              value: applications.filter((a) => a.status === "offer").length,
              color: "amber",
            },
          ].map((stat) => (
            <div key={stat.label} className="stat-card" data-color={stat.color}>
              <div className="stat-value">{stat.value}</div>
              <div className="stat-label">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Discovery */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Auto Job Discovery</div>
              <div className="card-subtitle">
                Scrape jobs from 9+ portals based on your profile
              </div>
            </div>
          </div>

          {!profileComplete ? (
            <div className="alert alert-warning">
              <strong>Setup required:</strong> Go to{" "}
              <a href="/profile">Profile</a> and set your Target Roles and
              Preferred Locations to enable auto discovery.
            </div>
          ) : (
            <>
              <div className="discovery-config">
                <div className="discovery-row">
                  <strong>Roles</strong>
                  <span>{user.target_roles.join(", ")}</span>
                </div>
                <div className="discovery-row">
                  <strong>Locations</strong>
                  <span>{user.preferred_locations.join(", ")}</span>
                </div>
                <div className="discovery-row">
                  <strong>Portals</strong>
                  <span>
                    {user.target_portals?.length
                      ? user.target_portals
                          .map((p) => SOURCE_LABELS[p] || p)
                          .join(", ")
                      : "LinkedIn, Naukri, Wellfound, Arc, GetOnBoard (default)"}
                  </span>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <button
                  onClick={handleDiscover}
                  disabled={discovering}
                  className="btn btn-primary"
                >
                  {discovering ? (
                    <><span className="spinner" /> Starting...</>
                  ) : (
                    "Find Jobs Now"
                  )}
                </button>
                <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                  Also runs every 6 hours automatically
                </span>
              </div>
            </>
          )}

          {discoverMsg && (
            <div
              className={`alert ${discoverMsg.startsWith("Error") ? "alert-danger" : "alert-success"}`}
              style={{ marginTop: 16 }}
            >
              {discovering && !discoverMsg.startsWith("Error") && (
                <span className="spinner" style={{ marginRight: 8 }} />
              )}
              {discoverMsg}
            </div>
          )}

          {runs.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                Recent Scans
              </div>
              {runs.slice(0, 5).map((run) => (
                <div key={run.id} className="discovery-run">
                  <span>
                    <span
                      className={`dot ${
                        run.status === "completed"
                          ? "dot-green"
                          : run.status === "running"
                            ? "dot-amber"
                            : "dot-red"
                      }`}
                    />
                    {run.status}
                  </span>
                  <span style={{ color: "var(--text-secondary)" }}>
                    {run.jobs_found} new jobs
                  </span>
                  <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                    {new Date(run.started_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Applications */}
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "20px 24px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)" }}>
            <div className="card-title">Recent Applications</div>
            {jobs.length > 0 && (
              <a href="/jobs" style={{ fontSize: 13 }}>
                View all {jobs.length} jobs
              </a>
            )}
          </div>

          {applications.length === 0 ? (
            <div className="empty-state">
              <p>No applications yet.</p>
              <p style={{ fontSize: 13 }}>
                Click &quot;Find Jobs Now&quot; to discover jobs, then go to
                Jobs to review matches and apply.
              </p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Company</th>
                    <th>Source</th>
                    <th>Match</th>
                    <th>Status</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {applications.map((app) => (
                    <tr key={app.id}>
                      <td style={{ fontWeight: 500 }}>{app.job.title}</td>
                      <td>{app.job.company}</td>
                      <td>
                        <span
                          className="badge badge-source"
                          style={{
                            background:
                              SOURCE_COLORS[app.job.source] || "#636e72",
                          }}
                        >
                          {SOURCE_LABELS[app.job.source] || app.job.source}
                        </span>
                      </td>
                      <td>
                        {app.match_score
                          ? `${Math.round(app.match_score)}%`
                          : "-"}
                      </td>
                      <td>
                        <span
                          className="badge badge-status"
                          style={{
                            background: `${STATUS_COLORS[app.status] || "#6b7280"}22`,
                            color: STATUS_COLORS[app.status] || "#6b7280",
                          }}
                        >
                          {app.status}
                        </span>
                      </td>
                      <td style={{ color: "var(--text-muted)", fontSize: 13 }}>
                        {app.applied_at
                          ? new Date(app.applied_at).toLocaleDateString()
                          : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
