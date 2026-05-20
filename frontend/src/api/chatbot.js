/**
 * AI Career Advisor chatbot — works with or without OpenAI key.
 * When no key is set, uses intelligent pattern-matched local responses.
 */

// ─── Smart Local AI Responses ─────────────────────────────────────────────
const KNOWLEDGE_BASE = {
  skills: {
    patterns: ['skill', 'learn', 'technology', 'programming', 'language', 'framework', 'what should i learn', 'which skill'],
    responses: [
      "Based on current job market trends, here are the most in-demand skills:\n\n🔥 **High Demand:**\n• Python — Most versatile language for data science, AI, and backend\n• JavaScript/React — Essential for web development\n• SQL — Required by 90%+ of data roles\n\n📈 **Rising Fast:**\n• Cloud (AWS/Azure/GCP) — Every company is migrating\n• Docker & Kubernetes — DevOps is booming\n• AI/ML — Huge demand for prompt engineering & LLMs\n\n💡 **My Advice:** Pick one area (web, data, or cloud) and go deep. Build 2-3 real projects to showcase your skills.",
      "Great question! Here's my recommended learning path based on what employers want:\n\n**Step 1:** Master one language deeply (Python or JavaScript)\n**Step 2:** Learn SQL + one database (PostgreSQL is versatile)\n**Step 3:** Build 3 portfolio projects\n**Step 4:** Learn Git, Docker, and CI/CD basics\n**Step 5:** Practice system design concepts\n\n🎯 Focus on building **real projects** over collecting certificates. A deployed app > 10 courses!",
      "Here's what top tech companies are looking for in 2024-2025:\n\n🏢 **FAANG/Big Tech:** DSA + System Design + 1 strong language\n🚀 **Startups:** Full-stack skills + ability to ship fast\n📊 **Data roles:** Python + SQL + Pandas + visualization\n🔒 **Security:** Networking + Linux + security frameworks\n\nUpload your resume and I'll give you personalized recommendations!"
    ]
  },
  resume: {
    patterns: ['resume', 'cv', 'cover letter', 'portfolio', 'apply', 'application'],
    responses: [
      "Here are proven resume tips that get interviews:\n\n✅ **Format:**\n• Keep it to 1 page (for internships)\n• Use clean, ATS-friendly format\n• Include GitHub/LinkedIn links\n\n📝 **Content:**\n• Start bullets with action verbs (Built, Designed, Implemented)\n• Quantify results: \"Reduced load time by 40%\" not \"Improved performance\"\n• List 3-5 relevant projects with tech stack used\n\n❌ **Avoid:**\n• Generic objectives — use a specific summary instead\n• Listing every technology you've touched once\n• Typos (have someone proofread!)\n\nUpload your resume on the Resume page and I'll analyze your skills!",
      "Here's how to write a compelling cover letter:\n\n**Opening:** Mention the exact role and why you're excited about the company\n\n**Body (2 paragraphs):**\n• Paragraph 1: Your most relevant project/experience that matches the role\n• Paragraph 2: Specific skills you bring and what you'll contribute\n\n**Closing:** Express enthusiasm and request a conversation\n\n💡 **Pro tip:** Reference something specific about the company (recent product launch, tech blog post, etc.) to show genuine interest.",
    ]
  },
  match: {
    patterns: ['match', 'score', 'improve', 'better', 'increase', 'percentage'],
    responses: [
      "Here's how to boost your match score:\n\n📊 **Understanding the Score:**\nYour match score is based on how many of the job's required skills overlap with skills detected in your resume.\n\n🚀 **To Improve:**\n1. **Upload an updated resume** — Include all your skills, even ones you think are obvious\n2. **Use exact keywords** — If a job needs \"React\", write \"React\" not \"React.js framework\"\n3. **Add relevant projects** — Each project adds to your detected skill set\n4. **Take skill-gap courses** — Check the Skill Gap page for personalized recommendations\n\n🎯 A score above 70% means you're a strong candidate. Above 50% is still worth applying!",
      "Your match score depends on skill overlap. Here's a quick guide:\n\n• **90-100%** — Perfect match! Apply immediately 🎯\n• **70-89%** — Strong candidate, highlight your matching skills\n• **50-69%** — Good fit, mention willingness to learn\n• **Below 50%** — Learn missing skills first, or apply if the role is a stretch goal\n\n**Quick wins to improve:**\n• Add certifications to your resume\n• Include ALL tech you've used in projects\n• List both the technology and the category (e.g., \"PostgreSQL (Database)\")"
    ]
  },
  company: {
    patterns: ['company', 'companies', 'target', 'where', 'which company', 'startup'],
    responses: [
      "Here's how to identify the best companies for your internship search:\n\n🎯 **Strategy:**\n1. **Start with your skills** — Search for companies using your tech stack\n2. **Check company size** — Startups = more learning, Big companies = more structure\n3. **Look at their engineering blog** — Companies that blog about tech value engineers\n\n🏢 **Top Internship Companies:**\n• **Big Tech:** Google, Microsoft, Amazon, Meta (competitive but great pay)\n• **Growing Tech:** Stripe, Shopify, Notion, Figma (great culture)\n• **Pakistan/South Asia:** Systems Limited, 10Pearls, Arbisoft, Netsol\n• **Remote-friendly:** GitLab, Automattic, Zapier, Buffer\n\n💡 Also check out the **Scrape Jobs** page to discover companies actively hiring!",
    ]
  },
  interview: {
    patterns: ['interview', 'prepare', 'question', 'coding', 'behavioral', 'technical'],
    responses: [
      "Here's your interview preparation checklist:\n\n💻 **Technical Interviews:**\n• Practice 2-3 LeetCode problems daily (Easy → Medium)\n• Focus on: Arrays, Strings, HashMaps, Trees, and Graphs\n• Use Python for coding interviews (cleaner syntax)\n• Practice explaining your thought process aloud\n\n🗣️ **Behavioral Interviews (STAR Method):**\n• **S**ituation — Set the context\n• **T**ask — What was your responsibility\n• **A**ction — What you specifically did\n• **R**esult — Quantifiable outcome\n\n📋 **Common Questions to Prepare:**\n• \"Tell me about a challenging project\"\n• \"How do you handle disagreements?\"\n• \"Why this company?\"\n• \"What's your biggest technical achievement?\"\n\n🎯 Practice mock interviews with friends or use Pramp.com!",
    ]
  },
  greeting: {
    patterns: ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'sup', 'what\'s up', 'howdy'],
    responses: [
      "Hey there! 👋 I'm your AI Career Advisor. Here's what I can help you with:\n\n🎯 **Career guidance** — Which skills to learn, which companies to target\n📝 **Resume tips** — How to make your resume stand out\n💼 **Interview prep** — Technical and behavioral interview strategies\n📊 **Match improvement** — How to boost your internship match scores\n\nWhat would you like to explore?",
    ]
  },
  general: {
    patterns: [],
    responses: [
      "That's a great question! Here are some general tips for your internship search:\n\n1. **Build a portfolio** — Deploy 2-3 projects on GitHub with READMEs\n2. **Network actively** — Connect with recruiters on LinkedIn\n3. **Apply broadly** — Don't wait for the 'perfect' match\n4. **Track applications** — Use the Applications page to stay organized\n5. **Keep learning** — Check the Skill Gap page for personalized recommendations\n\nFeel free to ask me about specific topics like skills, interviews, or resume writing!",
      "Here's what I'd recommend for students looking for internships:\n\n**Immediate Actions:**\n• Upload your latest resume to get AI skill matching\n• Use the Scrape Jobs page to discover new opportunities\n• Apply to at least 5 positions per week\n\n**Longer Term:**\n• Build a personal website/portfolio\n• Contribute to open source projects\n• Attend hackathons and tech meetups\n\nWant me to dive deeper into any of these topics?",
    ]
  }
}

function findLocalResponse(userMessage) {
  const msg = userMessage.toLowerCase()
  
  // Find the best matching category
  let bestMatch = null
  let bestScore = 0
  
  for (const [category, data] of Object.entries(KNOWLEDGE_BASE)) {
    if (category === 'general') continue
    const score = data.patterns.filter(p => msg.includes(p)).length
    if (score > bestScore) {
      bestScore = score
      bestMatch = category
    }
  }
  
  // Use general if no match found
  const category = bestMatch || 'general'
  const responses = KNOWLEDGE_BASE[category].responses
  const randomIndex = Math.floor(Math.random() * responses.length)
  return responses[randomIndex]
}

// ─── Send Message ─────────────────────────────────────────────────────────

export const sendMessage = async (messages, userSkills = []) => {
  const apiKey = import.meta.env.VITE_OPENAI_API_KEY

  const lastMessage = messages[messages.length - 1]?.content || ''

  // If no valid API key, use smart local responses
  if (!apiKey || apiKey === 'sk-your-openai-key-here' || apiKey.length < 20) {
    await new Promise((r) => setTimeout(r, 600 + Math.random() * 800))
    const response = findLocalResponse(lastMessage)
    
    // Personalize with user skills if available
    let personalizedResponse = response
    if (userSkills.length > 0 && response.includes('Upload your resume')) {
      personalizedResponse = response.replace(
        'Upload your resume',
        `Based on your skills (${userSkills.slice(0, 5).join(', ')}), you're on the right track! Upload your updated resume`
      )
    }
    
    return { content: personalizedResponse }
  }

  // Use OpenAI if key is available
  const systemPrompt = `You are an expert career advisor helping university students find internships. 
The user's skills are: ${userSkills.length > 0 ? userSkills.join(', ') : 'not yet detected — ask them to upload their resume'}.
Give specific, practical advice tailored to their background. Keep responses under 200 words. 
Be encouraging and actionable. Use emoji and markdown formatting for readability.
Focus on: skill development, resume tips, interview prep, and job search strategies.`

  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      max_tokens: 300,
      messages: [
        { role: 'system', content: systemPrompt },
        ...messages,
      ],
    }),
  })

  if (!response.ok) {
    // Fallback to local responses if API fails
    console.warn('OpenAI API failed, using local responses')
    return { content: findLocalResponse(lastMessage) }
  }

  const data = await response.json()
  return data.choices?.[0]?.message || { content: findLocalResponse(lastMessage) }
}
