import { createRouter, createWebHistory } from 'vue-router'
import SearchView from './views/SearchView.vue'
import StatusView from './views/StatusView.vue'
import SettingsView from './views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'search', component: SearchView },
    { path: '/status', name: 'status', component: StatusView },
    { path: '/settings', name: 'settings', component: SettingsView },
  ]
})

export default router
