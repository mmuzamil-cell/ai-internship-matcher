export default function Footer() {
  return (
    <footer className="border-t border-white/[0.04] py-6 px-6 mt-auto">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-slate-500 text-sm">
        <div className="flex items-center gap-2">
          <span className="font-display font-bold text-slate-400">
            Intern<span className="bg-gradient-to-r from-sky-400 to-blue-400 bg-clip-text text-transparent">IQ</span>
          </span>
          <span className="text-white/10">·</span>
          <span>AI-Powered Internship Matching</span>
        </div>
        <p>Final Year Project · {new Date().getFullYear()}</p>
      </div>
    </footer>
  )
}
