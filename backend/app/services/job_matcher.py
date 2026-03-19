"""
Job matching service — scores jobs against user profile.
Uses rule-based scoring (no LLM needed, fast and free).
"""

from app.models import User, Job


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def calculate_match_score(user: User, job: Job) -> tuple[float, list[str]]:
    """
    Calculate match score (0-100) between user profile and job.
    Blends rule-based scoring (70%) with semantic similarity (30%) when embeddings exist.
    Returns (score, list_of_reasons).
    """
    score = 0.0
    reasons = []
    max_possible = 0.0

    # 1. Skills match (40 points max)
    max_possible += 40
    if job.skills and user.skills:
        user_skill_names = {s.skill_name.lower() for s in user.skills}
        job_skill_names = {s.skill_name.lower() for s in job.skills}

        if job_skill_names:
            matched = user_skill_names & job_skill_names
            skill_ratio = len(matched) / len(job_skill_names)
            skill_score = skill_ratio * 40
            score += skill_score

            if matched:
                reasons.append(f"Skills match: {', '.join(matched)}")
            missing = job_skill_names - user_skill_names
            if missing:
                reasons.append(f"Missing skills: {', '.join(missing)}")
    elif not job.skills:
        # No skills listed in job, give partial credit
        score += 20
        reasons.append("Job has no specific skill requirements listed")

    # 2. Location match (20 points max)
    max_possible += 20
    if user.preferred_locations and job.location:
        job_loc = job.location.lower()
        user_locs = [loc.lower() for loc in user.preferred_locations]

        if any(loc in job_loc for loc in user_locs):
            score += 20
            reasons.append(f"Location match: {job.location}")
        elif "remote" in job_loc:
            score += 15
            reasons.append("Remote position available")
        else:
            reasons.append(f"Location mismatch: {job.location}")
    elif not job.location:
        score += 10

    # 3. Salary match (20 points max)
    max_possible += 20
    if user.salary_min and job.salary_max:
        if job.salary_max >= user.salary_min:
            score += 20
            reasons.append(f"Salary in range: {job.salary_min}-{job.salary_max} LPA")
        else:
            reasons.append(f"Salary below expectation: {job.salary_max} < {user.salary_min} LPA")
    elif job.salary_min is None and job.salary_max is None:
        score += 10  # Unknown salary, partial credit
        reasons.append("Salary not disclosed")

    # 4. Experience match (20 points max)
    max_possible += 20
    if user.years_of_experience is not None and job.description:
        desc_lower = job.description.lower()
        # Simple heuristic: look for experience mentions
        import re
        exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', desc_lower)
        if exp_match:
            required_years = int(exp_match.group(1))
            if user.years_of_experience >= required_years:
                score += 20
                reasons.append(f"Experience sufficient: {user.years_of_experience} >= {required_years} years")
            elif user.years_of_experience >= required_years - 1:
                score += 10
                reasons.append(f"Experience close: {user.years_of_experience} vs {required_years} required")
            else:
                reasons.append(f"Experience gap: {user.years_of_experience} vs {required_years} required")
        else:
            score += 15
            reasons.append("No specific experience requirement found")
    else:
        score += 10

    # Normalize to 0-100
    rule_score = round((score / max_possible) * 100, 1) if max_possible > 0 else 0

    # Blend with semantic similarity if both embeddings exist
    final_score = rule_score
    if (
        hasattr(user, "profile_embedding") and user.profile_embedding is not None
        and hasattr(job, "embedding") and job.embedding is not None
    ):
        try:
            user_emb = list(user.profile_embedding) if not isinstance(user.profile_embedding, list) else user.profile_embedding
            job_emb = list(job.embedding) if not isinstance(job.embedding, list) else job.embedding
            semantic_sim = _cosine_similarity(user_emb, job_emb)
            semantic_score = max(0, semantic_sim) * 100  # 0-100 scale
            final_score = round(rule_score * 0.7 + semantic_score * 0.3, 1)
            if semantic_sim > 0.5:
                reasons.append(f"Strong semantic match ({int(semantic_score)}%)")
        except Exception:
            pass

    return final_score, reasons
