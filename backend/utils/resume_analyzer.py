import json
import logging
import os
import re
import httpx

logger = logging.getLogger(__name__)

# List of strong action verbs
STRONG_VERBS = [
    "led", "built", "designed", "developed", "optimized", "implemented", "engineered",
    "scaled", "created", "launched", "managed", "improved", "solved", "automated",
    "streamlined", "conducted", "pioneered", "coordinated", "analyzed", "architected",
    "formulated", "established", "spearheaded", "executed", "collaborated"
]

# Alternate suggestions for weaker verbs
WEAK_TO_STRONG = {
    "helped": "assisted/collaborated/supported",
    "worked": "engineered/implemented/developed",
    "responsible": "spearheaded/managed/led",
    "got": "obtained/acquired/secured",
    "made": "created/designed/architected",
    "did": "executed/performed/conducted",
    "tried": "strived/aimed/attempted",
}

def analyze_resume_local(text: str) -> dict:
    """
    Perform local, rule-based ATS analysis of the resume text.
    Checks contact details, action verbs, quantified metrics, and section coverage.
    """
    text_lower = text.lower()
    
    categories = []
    
    # ── 1. Contact Information Check ──────────────────────────────────────────
    contact_feedback = []
    contact_score = 0
    
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    if email_match:
        contact_feedback.append("✅ Email address detected.")
        contact_score += 25
    else:
        contact_feedback.append("❌ No email address detected. Ensure your email is clearly visible at the top.")
        
    phone_match = re.search(r"\b(?:\+?\d{1,3}[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b|\b\d{10,11}\b", text)
    if phone_match:
        contact_feedback.append("✅ Phone number detected.")
        contact_score += 25
    else:
        contact_feedback.append("❌ No phone number detected. Recruiters need a way to call you.")
        
    linkedin_match = "linkedin.com" in text_lower
    if linkedin_match:
        contact_feedback.append("✅ LinkedIn profile link detected.")
        contact_score += 25
    else:
        contact_feedback.append("⚠️ LinkedIn profile link missing. A professional profile adds credibility.")
        
    github_match = "github.com" in text_lower
    if github_match:
        contact_feedback.append("✅ GitHub profile link detected.")
        contact_score += 25
    else:
        contact_feedback.append("⚠️ GitHub profile link missing. Essential for developers to showcase work.")
        
    contact_status = "success" if contact_score >= 75 else ("warning" if contact_score >= 50 else "danger")
    categories.append({
        "name": "Contact Information",
        "score": contact_score,
        "status": contact_status,
        "feedback": contact_feedback
    })

    # ── 2. Impact & Metrics Check ─────────────────────────────────────────────
    metrics_feedback = []
    
    # Regex to find percentages, currencies, or scale numbers (e.g. 50%, $10k, Rs 20000, 100+ users, 4 team members)
    metric_patterns = [
        r"\d+%",                    # percentages
        r"\$\d+",                   # US dollar
        r"\bRs\.?\s?\d+",           # Rupees
        r"\b\d+\+\s?(?:users|clients|projects|servers|dollars|million|billion|kb|mb|gb|tb|percent|x)\b", # scale indicators
        r"\b(?:improved|reduced|increased|saved|boosted)\s\w+\sby\s\d+\b" # action phrasing
    ]
    
    found_metrics = []
    for pattern in metric_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            found_metrics.extend(matches)
            
    num_metrics = len(found_metrics)
    metrics_score = min(100, num_metrics * 25)
    
    if num_metrics >= 3:
        metrics_feedback.append(f"✅ Great job! Found {num_metrics} quantified achievements (e.g., {', '.join(found_metrics[:3])}).")
    elif num_metrics > 0:
        metrics_feedback.append(f"⚠️ Found {num_metrics} quantified achievements. Adding more numeric results (e.g., 'reduced load time by 30%') strengthens your resume.")
    else:
        metrics_feedback.append("❌ No quantified achievements found. Recruiters look for measurable impact rather than just a list of tasks. Try adding percentages, dollar values, or user scale numbers.")

    metrics_status = "success" if metrics_score >= 75 else ("warning" if metrics_score >= 50 else "danger")
    categories.append({
        "name": "Impact & Metrics",
        "score": metrics_score,
        "status": metrics_status,
        "feedback": metrics_feedback
    })

    # ── 3. Action Verbs Check ─────────────────────────────────────────────────
    verbs_feedback = []
    found_verbs = []
    for verb in STRONG_VERBS:
        if re.search(rf"\b{verb}\b", text_lower):
            found_verbs.append(verb.capitalize())
            
    num_verbs = len(found_verbs)
    verbs_score = min(100, num_verbs * 15)
    
    if num_verbs >= 5:
        verbs_feedback.append(f"✅ Strong vocabulary! Used {num_verbs} active verbs (e.g., {', '.join(found_verbs[:5])}).")
    elif num_verbs > 0:
        verbs_feedback.append(f"⚠️ Found {num_verbs} active verbs. Try adding more powerful verbs (e.g., Optimized, Automated, Streamlined) at the beginning of your bullet points.")
    else:
        verbs_feedback.append("❌ No strong action verbs found. Avoid starting bullet points with passive phrases like 'Responsible for' or 'Helped with'. Use verbs like Developed, Implemented, or Spearheaded.")

    # Search for weak verbs in text to highlight
    weak_verbs_found = []
    for weak, strong in WEAK_TO_STRONG.items():
        if re.search(rf"\b{weak}\b", text_lower):
            weak_verbs_found.append(f"'{weak}' (replace with: {strong})")
            
    if weak_verbs_found:
        verbs_feedback.append(f"💡 Detected weaker verbs/phrases: {', '.join(weak_verbs_found[:3])}.")

    verbs_status = "success" if verbs_score >= 75 else ("warning" if verbs_score >= 50 else "danger")
    categories.append({
        "name": "Action Verbs",
        "score": verbs_score,
        "status": verbs_status,
        "feedback": verbs_feedback
    })

    # ── 4. Section Coverage Check ─────────────────────────────────────────────
    sections_feedback = []
    sections_found = 0
    
    sections = {
        "Education": ["education", "degree", "university", "college", "gpa"],
        "Experience": ["experience", "work history", "employment", "professional experience", "internship"],
        "Projects": ["project", "academic projects", "personal projects"],
        "Skills": ["skills", "technologies", "technical skills", "languages"]
    }
    
    for section_name, keywords in sections.items():
        has_section = False
        for kw in keywords:
            if kw in text_lower:
                has_section = True
                break
        if has_section:
            sections_found += 1
            sections_feedback.append(f"✅ Found {section_name} section.")
        else:
            sections_feedback.append(f"❌ Missing or unclear {section_name} section. Ensure this is labeled clearly.")
            
    sections_score = int((sections_found / 4) * 100)
    sections_status = "success" if sections_score >= 75 else ("warning" if sections_score >= 50 else "danger")
    categories.append({
        "name": "Formatting & Structure",
        "score": sections_score,
        "status": sections_status,
        "feedback": sections_feedback
    })

    # ── Overall Score & Grade ─────────────────────────────────────────────────
    total_score = int(sum(c["score"] for c in categories) / len(categories))
    
    # Check length
    word_count = len(text.split())
    length_feedback = ""
    if word_count < 250:
        total_score = max(10, total_score - 15)
        length_feedback = " Your resume is very short (under 250 words) — consider adding more detailed descriptions of your projects and courses."
    elif word_count > 900:
        total_score = max(10, total_score - 10)
        length_feedback = " Your resume is quite long (over 900 words). Try to condense it to fit on a single page, which is ideal for internships."
    else:
        length_feedback = " Word count is optimal (300-800 words), keeping it easy to read."

    # Determine Grade
    if total_score >= 90:
        grade = "A"
    elif total_score >= 80:
        grade = "B"
    elif total_score >= 70:
        grade = "C"
    elif total_score >= 50:
        grade = "D"
    else:
        grade = "F"
        
    if total_score % 10 >= 7 and grade != "A" and grade != "F":
        grade += "+"
    elif total_score % 10 < 3 and grade != "F" and grade != "A":
        grade += "-"

    # Add a standard list of bullet suggestions
    bullet_suggestions = []
    # Try to extract bullet points from text using regex
    bullets = re.findall(r"(?:^|[\n•\-\*])\s*([A-Z][^.\n]{15,100}\b(?:worked|helped|did|responsible|managed|built|made)\b[^.\n]{10,200})", text)
    for b in bullets:
        b_clean = b.strip()
        if "worked" in b_clean.lower() or "helped" in b_clean.lower() or "responsible" in b_clean.lower():
            # Make a strong replacement suggestion
            suggested = b_clean
            for weak, strong in WEAK_TO_STRONG.items():
                suggested = re.sub(rf"\b{weak}\b", strong.split("/")[0], suggested, flags=re.IGNORECASE)
            # Append some standard outcome to showcase impact
            suggested += ", improving efficiency by 15% and streamlining team workflows."
            bullet_suggestions.append({
                "original": b_clean,
                "suggestion": suggested
            })
            
    if not bullet_suggestions:
        # Fallback bullet suggestion
        bullet_suggestions.append({
            "original": "Worked on the frontend code and helped backend developers.",
            "suggestion": "Engineered responsive frontend UI views and collaborated with backend developers to integrate high-performance APIs, reducing user load times by 20%."
        })
        bullet_suggestions.append({
            "original": "Responsible for managing the database and writing queries.",
            "suggestion": "Spearheaded PostgreSQL database administration and optimized SQL query execution plans, enhancing system transaction speeds by 30%."
        })

    summary = f"Your resume has an overall score of {total_score}% ({grade})." + length_feedback
    if total_score < 70:
        summary += " Focus on adding quantified metrics, checking email/phone contact details, and using action-oriented verbs."
    else:
        summary += " It is in good shape! Minor tweaks to bullet points could make it stand out even more to employers."

    return {
        "score": total_score,
        "grade": grade,
        "summary": summary,
        "categories": categories,
        "bullet_suggestions": bullet_suggestions
    }

async def analyze_resume(text: str) -> dict:
    """
    Core entrypoint for resume ATS feedback.
    Tries OpenAI GPT-4o-mini if API key is set, otherwise falls back to local analyzer.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY not configured. Falling back to local rules-based analyzer.")
        return analyze_resume_local(text)

    # ── Call OpenAI API ──────────────────────────────────────────────────────────
    logger.info("Calling OpenAI API for resume feedback…")
    system_prompt = (
        "You are an elite Resume Reviewer and ATS Optimization Expert.\n"
        "Your task is to analyze the student's resume text and return a detailed, actionable review in JSON format.\n"
        "You must structure the JSON exactly as follows:\n"
        "{\n"
        "  \"score\": 85, // integer 0-100\n"
        "  \"grade\": \"A-\", // string grade (A+, A, A-, B+, B, B-, C+, C, C-, D, F)\n"
        "  \"summary\": \"Overall summary of feedback (approx 3 sentences)\",\n"
        "  \"categories\": [\n"
        "    {\n"
        "      \"name\": \"Contact Information\",\n"
        "      \"score\": 90, // integer 0-100\n"
        "      \"status\": \"success\", // success (>=75), warning (50-74), or danger (<50)\n"
        "      \"feedback\": [\"List of specific feedback points (1-3 sentences each)\"]\n"
        "    },\n"
        "    {\n"
        "      \"name\": \"Impact & Metrics\",\n"
        "      \"score\": 60,\n"
        "      \"status\": \"warning\",\n"
        "      \"feedback\": [\"Feedback on quantification, numbers, percentages...\"]\n"
        "    },\n"
        "    {\n"
        "      \"name\": \"Action Verbs\",\n"
        "      \"score\": 80,\n"
        "      \"status\": \"success\",\n"
        "      \"feedback\": [\"Feedback on vocabulary, strong active verbs vs passive phrasing...\"]\n"
        "    },\n"
        "    {\n"
        "      \"name\": \"Formatting & Structure\",\n"
        "      \"score\": 100,\n"
        "      \"status\": \"success\",\n"
        "      \"feedback\": [\"Feedback on section headers (Education, Experience, Projects, Skills) and formatting...\"]\n"
        "    }\n"
        "  ],\n"
        "  \"bullet_suggestions\": [\n"
        "    {\n"
        "      \"original\": \"Original bullet point from resume (should exist in text if possible)\",\n"
        "      \"suggestion\": \"A professional, impact-driven rewritten version of this bullet incorporating action verbs and metrics.\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "Ensure all feedback is constructive, specific, and tailored for entry-level internships."
    )

    try:
        # Use httpx to call OpenAI
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here is my resume text to analyze:\n\n{text[:6000]}"} # cap text input
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 1000
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if response.status_code == 200:
                try:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    # Validate required fields
                    if all(k in parsed for k in ("score", "grade", "summary", "categories")):
                        return parsed
                    logger.warning("OpenAI response missing required fields, falling back to local.")
                except (KeyError, IndexError, json.JSONDecodeError) as e:
                    logger.warning("Failed to parse OpenAI response: %s", e)
            else:
                logger.error("OpenAI API failed with status %d: %s", response.status_code, response.text)
    except Exception as e:
        logger.error("Error during OpenAI resume feedback API call: %s", e, exc_info=True)

    logger.info("OpenAI failed or timed out. Falling back to local rules-based analyzer.")
    return analyze_resume_local(text)
