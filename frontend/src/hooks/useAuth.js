import { useAuthStore } from '../store/authStore'

export const useAuth = () => {
  const { token, user, setAuth, setUser, logout, isAuthenticated, skills, setSkills } = useAuthStore()
  return { token, user, setAuth, setUser, logout, isAuthenticated: isAuthenticated(), skills, setSkills }
}
