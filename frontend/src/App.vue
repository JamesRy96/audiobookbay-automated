<template>
  <a class="skip-link" href="#main-content">Skip to content</a>
  <div class="app-shell__backdrop" aria-hidden="true"></div>
  <div class="app-shell__frame">
    <AppHeader />
    <main class="content" id="main-content">
      <router-view v-slot="{ Component }">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import AppHeader from './components/AppHeader.vue'
</script>

<style scoped>
.skip-link {
    position: absolute;
    left: 1rem;
    top: 1rem;
    z-index: 1001;
    padding: 0.75rem 1rem;
    border-radius: var(--radius-md);
    background: var(--accent);
    color: var(--accent-contrast);
    font-weight: 700;
    text-decoration: none;
    transform: translateY(-180%);
    transition: transform var(--transition);
}
.skip-link:focus {
    transform: translateY(0);
}
.content {
    display: grid;
    gap: 1.25rem;
    margin-top: 1rem;
    padding: 1.25rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    background: rgba(11, 16, 32, 0.66);
    box-shadow: var(--shadow-lg);
    backdrop-filter: blur(18px);
}
.content > :deep(*) {
    min-width: 0;
}

@media (max-width: 840px) {
    .content {
        padding: 1rem;
        border-radius: var(--radius-lg);
    }
}
</style>
