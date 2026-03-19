"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

const features = [
  {
    icon: "\u{1F50D}",
    title: "Auto Job Discovery",
    desc: "Scans LinkedIn, Naukri, Indeed & more every 6 hours",
  },
  {
    icon: "\u{1F3AF}",
    title: "Smart Matching",
    desc: "AI scores each job against your skills & preferences",
  },
  {
    icon: "\u{1F4C4}",
    title: "Resume Optimizer",
    desc: "Tailors your resume per job with ATS-friendly formatting",
  },
  {
    icon: "\u{1F399}\uFE0F",
    title: "Interview Prep",
    desc: "Generates role-specific questions so you walk in ready",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login({ email, password });
      localStorage.setItem("token", data.access_token);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-layout">
        {/* Left — Hero */}
        <div className="auth-hero">
          <div className="auth-hero-inner">
            <div className="auth-brand">
              Job<span>Flow</span>
            </div>
            <h1 className="auth-headline">
              Your AI-Powered Job Hunt,<br />on Autopilot
            </h1>
            <p className="auth-tagline">
              Stop spending hours scrolling job boards. JobFlow discovers roles that
              match you, optimizes your resume for each one, and prepares you for
              interviews — all automatically.
            </p>

            <div className="auth-features">
              {features.map((f) => (
                <div className="auth-feature" key={f.title}>
                  <span className="auth-feature-icon">{f.icon}</span>
                  <div>
                    <div className="auth-feature-title">{f.title}</div>
                    <div className="auth-feature-desc">{f.desc}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="auth-free-badge">100% Free — No credit card needed</div>
          </div>
        </div>

        {/* Right — Form */}
        <div className="auth-form-side">
          <div className="auth-card">
            <h2 className="auth-title">Welcome back</h2>
            <p className="auth-subtitle">Sign in to your account</p>

            <form onSubmit={handleSubmit}>
              {error && <div className="alert alert-danger">{error}</div>}

              <div className="form-group">
                <label className="form-label">Email</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary btn-lg btn-full"
              >
                {loading ? (
                  <>
                    <span className="spinner" /> Signing in...
                  </>
                ) : (
                  "Sign In"
                )}
              </button>
            </form>

            <p className="auth-footer">
              No account? <a href="/register">Create one free</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
