"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getMe, updateProfile, uploadResume, testNotification } from "@/lib/api";

const LOCATIONS = [
  "Bangalore", "Hyderabad", "Pune", "Mumbai",
  "Delhi NCR", "Chennai", "Remote", "Hybrid",
];

const PORTALS = [
  "linkedin", "naukri", "indeed", "wellfound", "arc",
  "torre", "getonboard", "google_jobs",
];

const PORTAL_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  naukri: "Naukri",
  indeed: "Indeed",
  wellfound: "Wellfound",
  arc: "Arc",
  torre: "Torre",
  getonboard: "GetOnBoard",
  google_jobs: "Google Jobs",
};

const PORTAL_DESCRIPTIONS: Record<string, string> = {
  linkedin: "Professional network",
  naukri: "India's #1 job site",
  indeed: "Global job search",
  wellfound: "Startup & remote jobs",
  arc: "Remote dev jobs",
  torre: "AI talent matching",
  getonboard: "Global tech startups",
  google_jobs: "Aggregated results",
};

export default function ProfilePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [testingEmail, setTestingEmail] = useState(false);
  const [form, setForm] = useState({
    full_name: "",
    phone: "",
    linkedin_url: "",
    years_of_experience: 0,
    salary_min: 0,
    salary_max: 0,
    preferred_locations: [] as string[],
    target_roles: "",
    target_companies: "",
    target_portals: [] as string[],
    email_notifications: true,
    notify_threshold: 60,
  });
  const [skills, setSkills] = useState([
    { skill_name: "", years_experience: 0, proficiency: "intermediate", is_primary: false },
  ]);
  const [certs, setCerts] = useState([
    { name: "", issuer: "", year_obtained: 2024 },
  ]);

  useEffect(() => {
    getMe()
      .then((user) => {
        setForm({
          full_name: user.full_name || "",
          phone: user.phone || "",
          linkedin_url: user.linkedin_url || "",
          years_of_experience: user.years_of_experience || 0,
          salary_min: user.salary_min || 0,
          salary_max: user.salary_max || 0,
          preferred_locations: user.preferred_locations || [],
          target_roles: (user.target_roles || []).join(", "),
          target_companies: (user.target_companies || []).join(", "),
          target_portals: user.target_portals || [],
          email_notifications: user.email_notifications ?? true,
          notify_threshold: user.notify_threshold ?? 60,
        });
        if (user.skills?.length) setSkills(user.skills);
        if (user.certifications?.length) setCerts(user.certifications);
        setLoading(false);
      })
      .catch(() => router.push("/login"));
  }, [router]);

  const handleSave = async () => {
    setSaving(true);
    setMsg("");
    try {
      await updateProfile({
        ...form,
        target_roles: form.target_roles
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        target_companies: form.target_companies
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        skills: skills.filter((s) => s.skill_name.trim()),
        certifications: certs.filter((c) => c.name.trim()),
      });
      setMsg("Profile saved successfully!");
    } catch (err) {
      setMsg(`Error: ${err instanceof Error ? err.message : "Save failed"}`);
    } finally {
      setSaving(false);
    }
  };

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await uploadResume(file);
      setMsg("Resume uploaded successfully!");
    } catch (err) {
      setMsg(`Error: ${err instanceof Error ? err.message : "Upload failed"}`);
    }
  };

  const toggleLocation = (loc: string) => {
    setForm((f) => ({
      ...f,
      preferred_locations: f.preferred_locations.includes(loc)
        ? f.preferred_locations.filter((l) => l !== loc)
        : [...f.preferred_locations, loc],
    }));
  };

  const togglePortal = (portal: string) => {
    setForm((f) => ({
      ...f,
      target_portals: f.target_portals.includes(portal)
        ? f.target_portals.filter((p) => p !== portal)
        : [...f.target_portals, portal],
    }));
  };

  if (loading)
    return (
      <div className="loading-page">
        <span className="spinner" /> Loading profile...
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
          <a href="/jobs">Jobs</a>
          <a href="/profile" className="active">Profile</a>
        </div>
      </nav>

      <div className="page-medium">
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>
            Profile Setup
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
            Configure your job search preferences
          </p>
        </div>

        {msg && (
          <div
            className={`alert ${msg.startsWith("Error") ? "alert-danger" : "alert-success"}`}
          >
            {msg}
          </div>
        )}

        {/* Target Roles - Highlighted */}
        <div className="card" style={{ borderColor: "var(--accent)" }}>
          <div className="card-title" style={{ marginBottom: 4 }}>
            Target Roles
          </div>
          <div className="card-subtitle" style={{ marginBottom: 12 }}>
            Required for auto-discovery. These job titles will be searched across all selected portals.
          </div>
          <input
            className="form-input"
            placeholder="DevOps Engineer, SRE, Platform Engineer, Kubernetes Engineer..."
            value={form.target_roles}
            onChange={(e) => setForm({ ...form, target_roles: e.target.value })}
          />
          <div className="form-hint">Comma-separated list of job titles</div>
        </div>

        {/* Locations */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            Preferred Locations
          </div>
          <div className="chip-group">
            {LOCATIONS.map((loc) => (
              <button
                key={loc}
                className={`chip ${form.preferred_locations.includes(loc) ? "active" : ""}`}
                onClick={() => toggleLocation(loc)}
              >
                {loc}
              </button>
            ))}
          </div>
        </div>

        {/* Portals */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 4 }}>
            Job Portals
          </div>
          <div className="card-subtitle" style={{ marginBottom: 12 }}>
            Select platforms to search for DevOps, SRE, Kubernetes, and Platform Engineering roles
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 8 }}>
            {PORTALS.map((p) => (
              <button
                key={p}
                className={`chip ${form.target_portals.includes(p) ? "active" : ""}`}
                onClick={() => togglePortal(p)}
                style={{ textAlign: "left", display: "flex", flexDirection: "column", alignItems: "flex-start", padding: "10px 14px" }}
              >
                <span style={{ fontWeight: 500 }}>{PORTAL_LABELS[p]}</span>
                <span style={{ fontSize: 11, opacity: 0.7 }}>{PORTAL_DESCRIPTIONS[p]}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Basic Info */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>
            Basic Info
          </div>
          <div className="form-group">
            <label className="form-label">Full Name</label>
            <input
              className="form-input"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Phone</label>
              <input
                className="form-input"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Years of Experience</label>
              <input
                type="number"
                className="form-input"
                value={form.years_of_experience}
                onChange={(e) =>
                  setForm({
                    ...form,
                    years_of_experience: parseInt(e.target.value) || 0,
                  })
                }
              />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">LinkedIn URL</label>
            <input
              className="form-input"
              value={form.linkedin_url}
              onChange={(e) =>
                setForm({ ...form, linkedin_url: e.target.value })
              }
              placeholder="https://linkedin.com/in/yourprofile"
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Min Salary (LPA)</label>
              <input
                type="number"
                className="form-input"
                value={form.salary_min}
                onChange={(e) =>
                  setForm({
                    ...form,
                    salary_min: parseInt(e.target.value) || 0,
                  })
                }
              />
            </div>
            <div className="form-group">
              <label className="form-label">Max Salary (LPA)</label>
              <input
                type="number"
                className="form-input"
                value={form.salary_max}
                onChange={(e) =>
                  setForm({
                    ...form,
                    salary_max: parseInt(e.target.value) || 0,
                  })
                }
              />
            </div>
          </div>
        </div>

        {/* Skills */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>
            Skills
          </div>
          {skills.map((skill, i) => (
            <div key={i} className="form-row" style={{ marginBottom: 8 }}>
              <div style={{ flex: 2 }}>
                <input
                  className="form-input"
                  placeholder="Skill name"
                  value={skill.skill_name}
                  onChange={(e) => {
                    const s = [...skills];
                    s[i] = { ...s[i], skill_name: e.target.value };
                    setSkills(s);
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <input
                  type="number"
                  className="form-input"
                  placeholder="Years"
                  value={skill.years_experience}
                  onChange={(e) => {
                    const s = [...skills];
                    s[i] = {
                      ...s[i],
                      years_experience: parseInt(e.target.value) || 0,
                    };
                    setSkills(s);
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <select
                  className="form-select"
                  value={skill.proficiency}
                  onChange={(e) => {
                    const s = [...skills];
                    s[i] = { ...s[i], proficiency: e.target.value };
                    setSkills(s);
                  }}
                >
                  <option value="beginner">Beginner</option>
                  <option value="intermediate">Intermediate</option>
                  <option value="expert">Expert</option>
                </select>
              </div>
            </div>
          ))}
          <button
            onClick={() =>
              setSkills([
                ...skills,
                {
                  skill_name: "",
                  years_experience: 0,
                  proficiency: "intermediate",
                  is_primary: false,
                },
              ])
            }
            className="btn btn-outline btn-sm"
            style={{ marginTop: 4 }}
          >
            + Add Skill
          </button>
        </div>

        {/* Certifications */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 16 }}>
            Certifications
          </div>
          {certs.map((cert, i) => (
            <div key={i} className="form-row" style={{ marginBottom: 8 }}>
              <div style={{ flex: 2 }}>
                <input
                  className="form-input"
                  placeholder="Certification name"
                  value={cert.name}
                  onChange={(e) => {
                    const c = [...certs];
                    c[i] = { ...c[i], name: e.target.value };
                    setCerts(c);
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <input
                  className="form-input"
                  placeholder="Issuer"
                  value={cert.issuer}
                  onChange={(e) => {
                    const c = [...certs];
                    c[i] = { ...c[i], issuer: e.target.value };
                    setCerts(c);
                  }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <input
                  type="number"
                  className="form-input"
                  placeholder="Year"
                  value={cert.year_obtained}
                  onChange={(e) => {
                    const c = [...certs];
                    c[i] = {
                      ...c[i],
                      year_obtained: parseInt(e.target.value) || 2024,
                    };
                    setCerts(c);
                  }}
                />
              </div>
            </div>
          ))}
          <button
            onClick={() =>
              setCerts([...certs, { name: "", issuer: "", year_obtained: 2024 }])
            }
            className="btn btn-outline btn-sm"
            style={{ marginTop: 4 }}
          >
            + Add Certification
          </button>
        </div>

        {/* Target Companies */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            Target Companies
          </div>
          <input
            className="form-input"
            placeholder="Google, Microsoft, Razorpay, Zerodha..."
            value={form.target_companies}
            onChange={(e) =>
              setForm({ ...form, target_companies: e.target.value })
            }
          />
          <div className="form-hint">Comma-separated list (optional)</div>
        </div>

        {/* Resume */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            Resume Upload
          </div>
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleResumeUpload}
            style={{ color: "var(--text-secondary)", fontSize: 14 }}
          />
          <div className="form-hint">PDF or DOCX, max 5MB</div>
        </div>

        {/* Notification Settings */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 4 }}>
            Email Notifications
          </div>
          <div className="card-subtitle" style={{ marginBottom: 16 }}>
            Get emailed when new jobs match your profile above your score threshold
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <button
              className={`chip ${form.email_notifications ? "active" : ""}`}
              onClick={() =>
                setForm({ ...form, email_notifications: !form.email_notifications })
              }
            >
              {form.email_notifications ? "Enabled" : "Disabled"}
            </button>
          </div>
          {form.email_notifications && (
            <>
              <div className="form-group">
                <label className="form-label">
                  Minimum Match Score: {form.notify_threshold}%
                </label>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={form.notify_threshold}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      notify_threshold: parseInt(e.target.value),
                    })
                  }
                  style={{ width: "100%", accentColor: "var(--accent)" }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-muted)" }}>
                  <span>All jobs (0%)</span>
                  <span>Best matches only (100%)</span>
                </div>
              </div>
              <button
                onClick={async () => {
                  setTestingEmail(true);
                  try {
                    await testNotification();
                    setMsg("Test email sent! Check your inbox.");
                  } catch (err) {
                    setMsg(
                      `Error: ${err instanceof Error ? err.message : "Failed to send test email"}`
                    );
                  } finally {
                    setTestingEmail(false);
                  }
                }}
                disabled={testingEmail}
                className="btn btn-outline btn-sm"
                style={{ marginTop: 8 }}
              >
                {testingEmail ? (
                  <><span className="spinner" /> Sending...</>
                ) : (
                  "Send Test Email"
                )}
              </button>
            </>
          )}
        </div>

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn btn-primary btn-lg btn-full"
          style={{ marginBottom: 40 }}
        >
          {saving ? (
            <><span className="spinner" /> Saving...</>
          ) : (
            "Save Profile"
          )}
        </button>
      </div>
    </>
  );
}
