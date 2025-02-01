import { createRouter, createWebHistory } from 'vue-router'
import { session } from './data/session'
import { userResource } from '@/data/user'
import store from "./store";

const routes = [
  {
    path: "/workspace",
    name: "Workspace",
    redirect: () => {
      window.location.href = "/app";
    },
  },
  {
    path: '/',
    name: 'ESS',
    component: () => import('@/pages/Home.vue'),
  },
  {
    name: 'Login',
    path: '/account/login',
    component: () => import('@/pages/Login.vue'),
  },
  {
    name: 'Ess',
    path: '/ess',
    component: () => import('@/pages/Home.vue'),
  },
]

let router = createRouter({
  history: createWebHistory('/ess'),
  routes,
})

router.beforeEach((to, from, next) => {
  if (to.matched.some((record) => record.meta.isPublicRoute)) {
    if (store.getters.isLoggedIn) {
      next({ name: "ESS" });
    } else {
      next();
    }
  } else {
    if (
      store.getters.isLoggedIn ||
      to.matched.some((record) => record.meta.isHybridRoute)
    ) {
      next();
    } else {
      import.meta.env.DEV ? next("/login") : (window.location.href = "/login");
    }
  }
});
// router.beforeEach(async (to, from, next) => {
//   let isLoggedIn = session.isLoggedIn
//   try {
//     await userResource.promise
//   } catch (error) {
//     isLoggedIn = false
//   }

//   if (to.name === 'Login' && isLoggedIn) {
//     next({ name: 'Home' })
//   } else if (to.name !== 'Login' && !isLoggedIn) {
//     next({ name: 'Login' })
//   } else {
//     next()
//   }
// })

export default router