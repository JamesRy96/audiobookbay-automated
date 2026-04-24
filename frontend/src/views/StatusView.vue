<template>
  <div class="title-container">
    <h1>Torrent Status</h1>
  </div>

  <div class="status-bar">
    <span class="connection-badge" :class="connectionClass">
      <span class="connection-dot"></span>
      {{ connectionLabel }}
    </span>
  </div>

  <p v-if="error" class="error-message">{{ error }}</p>

  <TorrentTable :torrents="torrents" />
</template>

<script setup lang="ts">
import { ref, computed, onActivated, onDeactivated, onMounted, onBeforeUnmount } from 'vue'
import type { TorrentStatus } from '@/types'
import { fetchStatus } from '@/api/client'
import TorrentTable from '@/components/TorrentTable.vue'

const FAST_INTERVAL = 3000
const NORMAL_INTERVAL = 15000
const FAST_DURATION = 30000

const torrents = ref<TorrentStatus[]>([])
const error = ref('')
const initialLoad = ref(true)
const connected = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null
let settleTimer: ReturnType<typeof setTimeout> | null = null

const connectionClass = computed(() => {
  if (initialLoad.value) return 'checking'
  return connected.value ? 'connected' : 'disconnected'
})

const connectionLabel = computed(() => {
  if (initialLoad.value) return 'Checking\u2026'
  return connected.value ? 'Connected' : 'Unreachable'
})

async function load() {
  try {
    torrents.value = await fetchStatus()
    connected.value = true
    error.value = ''
  } catch (e) {
    connected.value = false
    error.value = e instanceof Error ? e.message : 'Failed to load status'
  } finally {
    initialLoad.value = false
  }
}

function startPolling() {
  stopPolling()
  load()
  pollTimer = setInterval(load, FAST_INTERVAL)
  settleTimer = setTimeout(() => {
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(load, NORMAL_INTERVAL)
  }, FAST_DURATION)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (settleTimer) { clearTimeout(settleTimer); settleTimer = null }
}

onMounted(startPolling)
onActivated(startPolling)
onDeactivated(stopPolling)
onBeforeUnmount(stopPolling)
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
    max-width: 22ch;
    font-size: clamp(1.7rem, 1.3rem + 1.6vw, 2.8rem);
    line-height: 1.03;
    letter-spacing: -0.05em;
}

.status-bar {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
}

.connection-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}
.connection-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}

.connection-badge.connected {
    background: rgba(45, 212, 191, 0.14);
    color: #2dd4bf;
}
.connection-badge.connected .connection-dot {
    background: #2dd4bf;
}

.connection-badge.disconnected {
    background: rgba(248, 113, 113, 0.14);
    color: #f87171;
}
.connection-badge.disconnected .connection-dot {
    background: #f87171;
}

.connection-badge.checking {
    background: rgba(127, 139, 167, 0.14);
    color: #a9b4cc;
}
.connection-badge.checking .connection-dot {
    background: #a9b4cc;
    animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
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
</style>
