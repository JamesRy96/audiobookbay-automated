<template>
  <header class="app-header">
    <div class="app-brand" aria-label="AudiobookBay Automated">
      <span class="app-brand__eyebrow">Audiobook Manager</span>
      <span class="app-brand__title">AudiobookBay Automated</span>
    </div>
    <nav class="navbar" aria-label="Primary">
      <router-link to="/" :class="{ active: $route.name === 'search' }">Search</router-link>
      <router-link to="/status" :class="{ active: $route.name === 'status' }">Status</router-link>
      <router-link to="/settings" :class="{ active: $route.name === 'settings' }">Settings</router-link>
      <a
        v-if="navLinkName && navLinkUrl"
        :href="navLinkUrl"
        target="_blank"
        rel="noreferrer"
      >{{ navLinkName }}</a>
    </nav>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchConfig } from '@/api/client'

const navLinkName = ref<string | null>(null)
const navLinkUrl = ref<string | null>(null)

onMounted(async () => {
  try {
    const config = await fetchConfig()
    navLinkName.value = config.nav_link_name
    navLinkUrl.value = config.nav_link_url
  } catch {
    // nav link is optional
  }
})
</script>

<style scoped>
.app-header {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem 1.1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    background: var(--bg-elevated);
    box-shadow: var(--shadow-lg);
    backdrop-filter: blur(20px);
}
.app-brand {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
}
.app-brand__eyebrow {
    color: var(--accent-strong);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}
.app-brand__title {
    font-size: clamp(1.1rem, 0.9rem + 0.6vw, 1.45rem);
    font-weight: 700;
    letter-spacing: -0.03em;
}
.navbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
}
.navbar a {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.75rem;
    padding: 0.65rem 1rem;
    border: 1px solid transparent;
    border-radius: 999px;
    color: var(--text-muted);
    text-decoration: none;
    transition:
        transform var(--transition),
        border-color var(--transition),
        background-color var(--transition),
        color var(--transition),
        box-shadow var(--transition);
}
.navbar a:hover,
.navbar a:focus-visible {
    color: var(--text);
    background: rgba(255, 255, 255, 0.04);
    border-color: var(--border);
    box-shadow: var(--shadow-sm);
    transform: translateY(-1px);
}
.navbar a.active,
.navbar a.router-link-exact-active {
    color: var(--accent-contrast);
    background: linear-gradient(135deg, var(--accent), var(--accent-strong));
    border-color: transparent;
    box-shadow: 0 12px 28px rgba(79, 140, 255, 0.24);
}

@media (max-width: 840px) {
    .app-header {
        padding: 1rem;
        border-radius: var(--radius-lg);
    }
}
@media (max-width: 560px) {
    .navbar a {
        width: 100%;
    }
}
</style>
