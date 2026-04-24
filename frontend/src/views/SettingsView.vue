<template>
  <div class="title-container">
    <h1>Settings</h1>
  </div>

  <p v-if="error" class="error-message">{{ error }}</p>
  <p v-else-if="loading" class="loading-message">Loading settings…</p>

  <div v-else class="settings-grid">
    <div v-for="(value, key) in settings" :key="key" class="setting-card">
      <span class="setting-label">{{ formatLabel(String(key)) }}</span>
      <span class="setting-value" :class="{ empty: value === null || value === '' }">
        {{ formatValue(key, value) }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { AppSettings } from '@/types'
import { fetchSettings } from '@/api/client'

const settings = ref<AppSettings>({})
const loading = ref(true)
const error = ref('')

function formatLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\bdl\b/gi, 'Download')
}

function formatValue(key: string | number, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (String(key) === 'dl_password_configured') return value ? 'Yes' : 'No'
  return String(value)
}

onMounted(async () => {
  try {
    const data = await fetchSettings()
    if (data && typeof data === 'object' && 'settings' in data) {
      settings.value = (data as Record<string, unknown>).settings as AppSettings
    } else {
      settings.value = data
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load settings'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.title-container {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin: 0;
    text-align: left;
}
.title-container::after {
    content: "";
    width: 4.5rem;
    height: 0.2rem;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--accent), var(--accent-strong));
    opacity: 0.85;
}
.title-container h1 {
    margin: 0;
    font-size: clamp(1.7rem, 1.3rem + 1.6vw, 2.8rem);
    line-height: 1.03;
    letter-spacing: -0.05em;
}

.settings-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.75rem;
}
.setting-card {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.85rem 1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface);
}
.setting-label {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-subtle);
}
.setting-value {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text);
    word-break: break-all;
}
.setting-value.empty {
    color: var(--text-subtle);
}

.error-message {
    margin: 0;
    padding: 0.85rem 1rem;
    border: 1px solid rgba(248, 113, 113, 0.3);
    border-radius: var(--radius-md);
    background: rgba(248, 113, 113, 0.08);
    color: #ffb5b5;
    font-weight: 600;
}
.loading-message {
    color: var(--text-muted);
}
</style>
