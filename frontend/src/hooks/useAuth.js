import { useAuthStore } from '../store/authStore'

export const useAuth = () => {
  const { token, user, setAuth, setUser, logout, skills, setSkills } = useAuthStore()
  // Derive isAuthenticated from token directly so Zustand re-renders on change
  return { token, user, setAuth, setUser, logout, isAuthenticated: Boolean(token), skills, setSkills }
}
