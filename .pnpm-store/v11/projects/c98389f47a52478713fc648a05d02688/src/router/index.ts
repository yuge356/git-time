import { createRouter, createWebHistory } from 'vue-router'

import { pinia } from '@/stores'
import { useAuthStore } from '@/stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'welcome',
      component: () => import('@/views/WelcomeView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/onboarding',
      name: 'onboarding',
      component: () => import('@/views/OnboardingView.vue'),
      meta: { requiresAuth: true, onboardingOnly: true },
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: () => import('@/views/TasksView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/today',
      name: 'today',
      component: () => import('@/views/TodayView.vue'),
      meta: { requiresAuth: true },
    },
    {
      // Merged into the today view — keep old links working.
      path: '/timer',
      redirect: '/today',
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: () => import('@/views/AnalyticsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/partners',
      name: 'partners',
      component: () => import('@/views/PartnersView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/sharing',
      redirect: '/partners',
    },
    {
      path: '/notifications',
      name: 'notifications',
      component: () => import('@/views/NotificationsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      redirect: { name: 'login', query: { mode: 'register' } },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)
  await auth.initialize()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (auth.requiresOnboarding && to.name !== 'onboarding') {
    const redirect = to.meta.requiresAuth ? to.fullPath : undefined
    return {
      name: 'onboarding',
      ...(redirect ? { query: { redirect } } : {}),
    }
  }
  if (to.meta.onboardingOnly && auth.isAuthenticated && !auth.requiresOnboarding) {
    return { name: 'today' }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'today' }
  }
  return true
})
