"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { register } from "@/lib/api";

const benefits = [
  "Discovers jobs from 8+ portals automatically",
  "AI-powered resume tailoring per job",
  "Smart match scoring so you apply to the right roles",
  "Interview prep with role-specific questions",
  "Completely free — no hidden charges",
];

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await register(form);
      localStorage.setItem("token", data.access_token);
      router.push("/profile");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
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
              Land Your Next Role,<br />Faster
            </h1>
            <p className="auth-tagline">
              Join JobFlow and let AI handle the tedious parts of job hunting —
              from finding matching roles to tailoring your resume — so you can
              focus on what matters: acing the interview.
            </p>

            <ul className="auth-benefits">
              {benefits.map((b) => (
                <li key={b} className="auth-benefit">
                  <span className="auth-benefit-check">{"\u2713"}</span>
                  {b}
                </li>
              ))}
            </ul>

            <div className="auth-free-badge">100% Free — No credit card needed</div>
          </div>
        </div>

        {/* Right — Form */}
        <div className="auth-form-side">
          <div className="auth-card">
            <h2 className="auth-title">Create your account</h2>
            <p className="auth-subtitle">Get started in under a minute</p>

            <form onSubmit={handleSubmit}>
              {error && <div className="alert alert-danger">{error}</div>}

              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  className="form-input"
                  placeholder="Your full name"
                  value={form.full_name}
                  onChange={(e) =>
                    setForm({ ...form, full_name: e.target.value })
                  }
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Email</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="you@example.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="Min 8 characters"
                  value={form.password}
                  onChange={(e) =>
                    setForm({ ...form, password: e.target.value })
                  }
                  required
                  minLength={8}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn btn-primary btn-lg btn-full"
              >
                {loading ? (
                  <>
                    <span className="spinner" /> Creating account...
                  </>
                ) : (
                  "Create Free Account"
                )}
              </button>
            </form>

            <p className="auth-footer">
              Already have an account? <a href="/login">Sign in</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
