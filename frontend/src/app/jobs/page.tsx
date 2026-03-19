"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  matchJobs,
  optimizeResume,
  applyToJob,
  getInterviewPrep,
  generateCoverLetter,
  autoApply,
} from "@/lib/api";

interface JobSkill {
  skill_name: string;
}

interface Job {
  id: number;
  title: string;
  company: string;
  location: string | null;
  salary_min: number | null;
  salary_max: number | null;
  description: string | null;
  job_url: string | null;
  source: string;
  skills: JobSkill[];
}

interface MatchedJob {
  job: Job;
  match_score: number;
  match_reasons: string[];
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

export default function JobsPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<MatchedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<MatchedJob | null>(null);
  const [actionMsg, setActionMsg] = useState("");
  const [actionLoading, setActionLoading] = useState("");
  const [applyingJobId, setApplyingJobId] = useState<number | null>(null);
  const [interviewQ, setInterviewQ] = useState("");
  const [coverLetter, setCoverLetter] = useState("");
  const [coverLetterPath, setCoverLetterPath] = useState("");

  useEffect(() => {
    matchJobs(50)
      .then(setJobs)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  const handleOptimize = async (jobId: number) => {
    setActionLoading("optimize");
    setActionMsg("");
    try {
      const resume = await optimizeResume(jobId);
      setActionMsg(`Resume optimized! File: ${resume.original_filename}`);
    } catch (err) {
      setActionMsg(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setActionLoading("");
    }
  };

  const handleApply = async (jobId: number, jobUrl?: string | null) => {
    setActionLoading("apply");
    setApplyingJobId(jobId);
    setActionMsg("");
    try {
      await applyToJob(jobId);
      setActionMsg("Application tracked!");
      if (jobUrl) {
        window.open(jobUrl, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      setActionMsg(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setActionLoading("");
      setApplyingJobId(null);
    }
  };

  const handleInterview = async (jobId: number) => {
    setActionLoading("interview");
    setInterviewQ("");
    try {
      const result = await getInterviewPrep(jobId);
      setInterviewQ(result.questions);
    } catch (err) {
      setInterviewQ(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setActionLoading("");
    }
  };

  const handleCoverLetter = async (jobId: number) => {
    setActionLoading("coverletter");
    setCoverLetter("");
    setCoverLetterPath("");
    setActionMsg("");
    try {
      const result = await generateCoverLetter(jobId);
      setCoverLetter(result.content);
      setCoverLetterPath(result.file_path);
      setActionMsg("Cover letter generated!");
    } catch (err) {
      setActionMsg(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setActionLoading("");
    }
  };

  const handleAutoApply = async (jobId: number) => {
    setActionLoading("autoapply");
    setApplyingJobId(jobId);
    setActionMsg("");
    try {
      const result = await autoApply(jobId);
      setActionMsg(`Auto-apply started: ${result.message}`);
    } catch (err) {
      setActionMsg(`Error: ${err instanceof Error ? err.message : "Failed"}`);
    } finally {
      setActionLoading("");
      setApplyingJobId(null);
    }
  };

  const getScoreClass = (score: number) => {
    if (score >= 75) return "score-high";
    if (score >= 50) return "score-mid";
    return "score-low";
  };

  if (loading)
    return (
      <div className="loading-page">
        <span className="spinner" /> Loading matched jobs...
      </div>
    );

  return (
    <>
      <nav className="navbar">
        <div className="navbar-brand">
          <span>Job</span>Flow
        </div>
        <div className="navbar-links">
          <a href="/dashboard">Dashboard</a>
          <a href="/jobs" className="active">Jobs</a>
          <a href="/profile">Profile</a>
        </div>
      </nav>

      <div className="page">
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>
            Job Matches
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
            {jobs.length} jobs ranked by match score
          </p>
        </div>

        {actionMsg && (
          <div
            className={`alert ${actionMsg.startsWith("Error") ? "alert-danger" : "alert-success"}`}
          >
            {actionMsg}
          </div>
        )}

        <div className={selectedJob ? "two-col" : "one-col"} style={{ display: "grid", gap: 20 }}>
          {/* Job List */}
          <div>
            {jobs.length === 0 ? (
              <div className="empty-state">
                <p>No jobs found yet.</p>
                <p style={{ fontSize: 13 }}>
                  Run job discovery from the dashboard to find matches.
                </p>
                <a href="/dashboard" className="btn btn-primary" style={{ marginTop: 12 }}>
                  Go to Dashboard
                </a>
              </div>
            ) : (
              jobs.map((mj) => (
                <div
                  key={mj.job.id}
                  className={`job-card ${selectedJob?.job.id === mj.job.id ? "selected" : ""}`}
                  onClick={() => setSelectedJob(mj)}
                >
                  <div className="job-card-row">
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="job-card-title">{mj.job.title}</div>
                      <div className="job-card-meta">
                        <span>{mj.job.company}</span>
                        {mj.job.location && (
                          <span>{mj.job.location}</span>
                        )}
                        <span
                          className="badge badge-source"
                          style={{
                            background: SOURCE_COLORS[mj.job.source] || "#636e72",
                          }}
                        >
                          {SOURCE_LABELS[mj.job.source] || mj.job.source}
                        </span>
                      </div>
                    </div>
                    <div className={`score-circle ${getScoreClass(mj.match_score)}`}>
                      {Math.round(mj.match_score)}%
                    </div>
                  </div>
                  {mj.job.skills.length > 0 && (
                    <div className="job-card-skills">
                      {mj.job.skills.slice(0, 6).map((s) => (
                        <span key={s.skill_name} className="skill-tag">
                          {s.skill_name}
                        </span>
                      ))}
                    </div>
                  )}
                  <div
                    className="job-card-actions"
                    style={{ display: "flex", gap: 8, marginTop: 10 }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      onClick={() => handleApply(mj.job.id, mj.job.job_url)}
                      disabled={actionLoading === "apply" && applyingJobId === mj.job.id}
                      className="btn btn-success btn-sm"
                      style={{ fontSize: 12, padding: "4px 12px" }}
                    >
                      {actionLoading === "apply" && applyingJobId === mj.job.id
                        ? "Applying..."
                        : "Apply"}
                    </button>
                    {mj.job.job_url && (
                      <a
                        href={mj.job.job_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-outline btn-sm"
                        style={{ fontSize: 12, padding: "4px 12px" }}
                      >
                        View Original
                      </a>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Detail Panel */}
          {selectedJob && (
            <div className="detail-panel">
              <h2>{selectedJob.job.title}</h2>
              <div className="detail-panel-meta">
                {selectedJob.job.company}
                {selectedJob.job.location
                  ? ` \u2022 ${selectedJob.job.location}`
                  : ""}
              </div>

              {selectedJob.job.salary_min && (
                <div style={{ fontSize: 14, color: "var(--success)", fontWeight: 600, marginBottom: 16 }}>
                  {selectedJob.job.salary_min}-{selectedJob.job.salary_max} LPA
                </div>
              )}

              <div className="detail-section">
                <h4>Match Analysis</h4>
                <ul style={{ paddingLeft: 18, color: "var(--text-secondary)", fontSize: 14 }}>
                  {selectedJob.match_reasons.map((r, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>{r}</li>
                  ))}
                </ul>
              </div>

              {selectedJob.job.description && (
                <div className="detail-section">
                  <h4>Description</h4>
                  <div className="detail-description">
                    {selectedJob.job.description}
                  </div>
                </div>
              )}

              <div className="detail-actions">
                <button
                  onClick={() => handleOptimize(selectedJob.job.id)}
                  disabled={actionLoading === "optimize"}
                  className="btn btn-primary btn-sm"
                >
                  {actionLoading === "optimize" ? (
                    <><span className="spinner" /> Optimizing...</>
                  ) : (
                    "Optimize Resume"
                  )}
                </button>
                <button
                  onClick={() => handleApply(selectedJob.job.id, selectedJob.job.job_url)}
                  disabled={actionLoading === "apply"}
                  className="btn btn-success btn-sm"
                >
                  {actionLoading === "apply" ? "Applying..." : "Apply"}
                </button>
                <button
                  onClick={() => handleCoverLetter(selectedJob.job.id)}
                  disabled={actionLoading === "coverletter"}
                  className="btn btn-outline btn-sm"
                >
                  {actionLoading === "coverletter" ? (
                    <><span className="spinner" /> Writing...</>
                  ) : (
                    "Cover Letter"
                  )}
                </button>
                <button
                  onClick={() => handleInterview(selectedJob.job.id)}
                  disabled={actionLoading === "interview"}
                  className="btn btn-purple btn-sm"
                >
                  {actionLoading === "interview" ? (
                    <><span className="spinner" /> Generating...</>
                  ) : (
                    "Interview Prep"
                  )}
                </button>
                {(selectedJob.job.source === "linkedin" || selectedJob.job.source === "naukri") && selectedJob.job.job_url && (
                  <button
                    onClick={() => handleAutoApply(selectedJob.job.id)}
                    disabled={actionLoading === "autoapply"}
                    className="btn btn-success btn-sm"
                    style={{ background: "#059669" }}
                  >
                    {actionLoading === "autoapply" ? (
                      <><span className="spinner" /> Auto Applying...</>
                    ) : (
                      "Auto Apply"
                    )}
                  </button>
                )}
                {selectedJob.job.job_url && (
                  <a
                    href={selectedJob.job.job_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-outline btn-sm"
                  >
                    View Original
                  </a>
                )}
              </div>

              {coverLetter && (
                <div className="interview-box" style={{ marginTop: 16 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--text-primary)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span>Cover Letter</span>
                    {coverLetterPath && (
                      <a
                        href={`${(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001").replace("/api", "")}/uploads/resumes/${coverLetterPath.split("/").pop()}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-outline btn-sm"
                        style={{ fontSize: 11, padding: "2px 8px" }}
                      >
                        Download PDF
                      </a>
                    )}
                  </div>
                  <div style={{ whiteSpace: "pre-wrap" }}>{coverLetter}</div>
                </div>
              )}

              {interviewQ && (
                <div className="interview-box" style={{ marginTop: 16 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, color: "var(--text-primary)" }}>
                    Interview Questions
                  </div>
                  {interviewQ}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
