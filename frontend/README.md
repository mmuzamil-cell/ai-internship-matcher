# InternIQ — AI-Powered Internship Matcher Frontend

A modern React frontend for the InternIQ internship matching platform. Connects to a FastAPI backend at `localhost:8000` and integrates with OpenAI for the AI Career Advisor chatbot.

---

## ⚡ Quick Start

### 1. Install dependencies

```bash
cd internship-matcher
npm install
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
VITE_API_URL=http://localhost:8000
VITE_OPENAI_API_KEY=sk-your-openai-key-here
```

> If you don't have an OpenAI key, the chatbot will still work with a fallback demo response.

### 3. Start the dev server

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### 4. Build for production

```bash
npm run build
npm run preview
```

---

## 🏗 Project Structure

```
src/
├── api/
│   ├── client.js         # Axios instance with JWT interceptors
│   ├── auth.js           # register, login, getMe, updateProfile
│   ├── resume.js         # uploadResume, getMyResumes, deleteResume
│   ├── jobs.js           # getJobs, getJobById, getJobStats
│   ├── matching.js       # getMyMatches, getSkillGap
│   ├── applications.js   # applyToJob, getMyApplications, updateStatus
│   └── chatbot.js        # sendMessage → OpenAI GPT-4o-mini
│
├── components/
│   ├── layout/
│   │   ├── Navbar.jsx    # Top nav with user menu
│   │   ├── Sidebar.jsx   # Collapsible left sidebar (mobile drawer)
│   │   └── Footer.jsx
│   └── ui/
│       ├── MatchScoreBadge.jsx  # Circular SVG score badge
│       ├── SkillTag.jsx         # Pill badge (matched/missing/learning)
│       ├── JobCard.jsx          # Full internship card with quick apply
│       ├── LoadingSpinner.jsx
│       └── EmptyState.jsx
│
├── pages/
│   ├── auth/
│   │   ├── Login.jsx     # JWT login with error handling
│   │   └── Register.jsx  # Registration with auto-login
│   ├── dashboard/
│   │   ├── Dashboard.jsx     # Overview stats + charts
│   │   ├── MyMatches.jsx     # AI-ranked matches with filters
│   │   ├── JobDetail.jsx     # Full job page with match analysis
│   │   ├── ResumeUpload.jsx  # Drag & drop PDF upload
│   │   ├── Applications.jsx  # Kanban board with DnD
│   │   ├── SkillGap.jsx      # Gap analysis + course recommendations
│   │   └── Profile.jsx       # Edit profile
│   ├── Chatbot.jsx           # Floating AI career advisor
│   └── NotFound.jsx
│
├── store/
│   └── authStore.js      # Zustand store (token, user, skills)
│
├── hooks/
│   ├── useAuth.js
│   └── useJobs.js
│
└── utils/
    ├── formatDate.js
    └── formatScore.js
```

---

## 🔌 Backend API Endpoints Expected

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | OAuth2 token login |
| GET | `/auth/me` | Get current user |
| PUT | `/auth/me` | Update profile |
| POST | `/resumes/upload` | Upload PDF resume |
| GET | `/resumes/my-resumes` | List uploaded resumes |
| DELETE | `/resumes/{id}` | Delete a resume |
| GET | `/jobs` | List jobs (with filters) |
| GET | `/jobs/{id}` | Single job detail |
| GET | `/jobs/stats` | Aggregate stats |
| GET | `/match/my-matches` | AI-matched jobs |
| GET | `/match/skill-gap` | Skill gap analysis |
| POST | `/applications` | Submit application |
| GET | `/applications/my-applications` | My applications |
| PUT | `/applications/{id}` | Update status/notes |

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 18 + Vite |
| Routing | React Router v6 |
| State | Zustand |
| Data Fetching | TanStack Query v5 |
| Styling | Tailwind CSS v3 |
| Animations | Framer Motion |
| Charts | Chart.js + react-chartjs-2 |
| Drag & Drop | @dnd-kit/core |
| Toasts | react-hot-toast |
| HTTP | Axios |
| AI Chat | OpenAI GPT-4o-mini |

---

## 🌐 Connecting to Your Backend

The Axios client (`src/api/client.js`) automatically:
- Attaches `Authorization: Bearer <token>` to every request
- Redirects to `/login` on 401 responses
- Extracts `error.response.data.detail` for user-friendly error toasts

If your Celery scraper populates jobs daily, the dashboard will reflect fresh data on each page load (React Query has a 2-minute stale time by default — adjust in `App.jsx`).

---

## 🎨 Customization

- **Colors**: Edit `tailwind.config.js` → `theme.extend.colors`
- **API URL**: Set `VITE_API_URL` in `.env`
- **Query cache time**: Edit `staleTime` in `App.jsx` QueryClient config
- **Dark mode**: Toggle via `.dark` class on `<html>` (Tailwind dark mode is set to `class`)
