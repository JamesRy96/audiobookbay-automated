<template>
  <table v-if="torrents.length > 0">
    <thead>
      <tr>
        <th>Title</th>
        <th>Progress</th>
        <th>State</th>
        <th>Size</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(torrent, i) in torrents" :key="i">
        <td class="title-cell">{{ torrent.name }}</td>
        <td>
          <div class="progress-cell">
            <svg class="progress-ring" viewBox="0 0 36 36">
              <circle class="progress-ring__bg" cx="18" cy="18" r="15.5" />
              <circle
                class="progress-ring__fill"
                cx="18" cy="18" r="15.5"
                :style="{
                  strokeDashoffset: ringOffset(torrent.progress),
                  stroke: stateColor(torrent.state),
                }"
              />
            </svg>
            <span class="progress-text">{{ torrent.progress }}%</span>
          </div>
        </td>
        <td>
          <span class="state-badge" :style="{ '--badge-color': stateColor(torrent.state) }">
            <span class="state-dot"></span>
            {{ stateLabel(torrent.state) }}
          </span>
        </td>
        <td>{{ torrent.size }}</td>
      </tr>
    </tbody>
  </table>
  <p v-else class="empty-state">No active torrents.</p>
</template>

<script setup lang="ts">
import type { TorrentStatus } from '@/types'

defineProps<{ torrents: TorrentStatus[] }>()

const CIRCUMFERENCE = 2 * Math.PI * 15.5

function ringOffset(progress: number): number {
  return CIRCUMFERENCE - (progress / 100) * CIRCUMFERENCE
}

const STATE_MAP: Record<string, { label: string; color: string }> = {
  downloading:        { label: 'Downloading', color: '#4f8cff' },
  stalleddl:          { label: 'Downloading', color: '#4f8cff' },
  forceddl:           { label: 'Downloading', color: '#4f8cff' },
  metadl:             { label: 'Fetching',    color: '#4f8cff' },
  allocating:         { label: 'Allocating',  color: '#4f8cff' },

  uploading:          { label: 'Seeding',     color: '#2dd4bf' },
  stalledup:          { label: 'Seeding',     color: '#2dd4bf' },
  forcedup:           { label: 'Seeding',     color: '#2dd4bf' },
  seeding:            { label: 'Seeding',     color: '#2dd4bf' },
  

  pauseddl:           { label: 'Paused',      color: '#f5b942' },
  pausedup:           { label: 'Paused',      color: '#f5b942' },
  stopped:            { label: 'Stopped',     color: '#f5b942' },
  paused:             { label: 'Paused',      color: '#f5b942' },

  queueddl:           { label: 'Queued',      color: '#7f8ba7' },
  queuedup:           { label: 'Queued',      color: '#7f8ba7' },
  queued:             { label: 'Queued',      color: '#7f8ba7' },

  checkingdl:         { label: 'Checking',    color: '#7f8ba7' },
  checkingup:         { label: 'Checking',    color: '#7f8ba7' },
  checkingresumedata: { label: 'Checking',    color: '#7f8ba7' },
  checking:           { label: 'Checking',    color: '#7f8ba7' },

  error:              { label: 'Error',       color: '#f87171' },
  missingfiles:       { label: 'Missing',     color: '#f87171' },

  completed:          { label: 'Complete',    color: '#2dd4bf' },
  complete:           { label: 'Complete',    color: '#2dd4bf' },
  stoppedup:          { label: 'Complete',    color: '#2dd4bf' },
}

function stateLabel(raw: string): string {
  return STATE_MAP[raw.toLowerCase()]?.label ?? raw
}

function stateColor(raw: string): string {
  return STATE_MAP[raw.toLowerCase()]?.color ?? '#7f8ba7'
}
</script>

<style scoped>
table {
    width: 100%;
    border-collapse: collapse;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: var(--surface-strong);
    box-shadow: var(--shadow-md);
}
th, td {
    padding: 0.95rem 1rem;
    text-align: left;
    vertical-align: middle;
    border-bottom: 1px solid rgba(160, 177, 214, 0.12);
}
th {
    color: var(--text-muted);
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    background: rgba(255, 255, 255, 0.025);
}
tr:hover td {
    background: rgba(255, 255, 255, 0.025);
}
.title-cell {
    max-width: 30ch;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.progress-cell {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.progress-ring {
    width: 28px;
    height: 28px;
    transform: rotate(-90deg);
    flex-shrink: 0;
}
.progress-ring__bg {
    fill: none;
    stroke: rgba(255, 255, 255, 0.08);
    stroke-width: 3;
}
.progress-ring__fill {
    fill: none;
    stroke-width: 3;
    stroke-linecap: round;
    stroke-dasharray: 97.39;
    transition: stroke-dashoffset 0.4s ease, stroke 0.3s ease;
}
.progress-text {
    font-size: 0.85rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--text-muted);
    white-space: nowrap;
}

.state-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--badge-color) 14%, transparent);
    color: var(--badge-color);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}
.state-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--badge-color);
    flex-shrink: 0;
}

.empty-state {
    color: var(--text-muted);
    text-align: center;
    padding: 2rem;
}
</style>
