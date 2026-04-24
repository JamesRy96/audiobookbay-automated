<template>
  <div class="filter-container" v-if="books.length > 0">
    <div class="filter-row">
      <div class="filter-controls">
        <select v-model="language">
          <option value="">All Languages</option>
          <option v-for="lang in languages" :key="lang" :value="lang">{{ lang }}</option>
        </select>
        <select v-model="bitrate">
          <option value="">All Bitrates</option>
          <option v-for="br in bitrates" :key="br" :value="br">{{ br }}</option>
        </select>
        <select v-model="format">
          <option value="">All Formats</option>
          <option v-for="fmt in formats" :key="fmt" :value="fmt">{{ fmt }}</option>
        </select>
        <input
          ref="dateInput"
          type="text"
          placeholder="Select Date Range"
          readonly
        />
      </div>
      <div class="filter-buttons">
        <button @click="applyFilters">Filter</button>
      </div>
    </div>
    <div class="filter-row">
      <div class="filter-controls">
        <div class="file-size-filter-wrapper" v-if="sizeRange">
          <label>File Size:</label>
          <div ref="sliderEl"></div>
        </div>
      </div>
      <div class="filter-buttons">
        <button @click="clearFilters">Clear</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import type { BookResult } from '@/types'
import flatpickr from 'flatpickr'
import 'flatpickr/dist/flatpickr.min.css'
import noUiSlider, { type API as SliderAPI } from 'nouislider'
import 'nouislider/dist/nouislider.css'

const props = defineProps<{ books: BookResult[] }>()
const emit = defineEmits<{ filtered: [books: BookResult[]] }>()

const language = ref('')
const bitrate = ref('')
const format = ref('')
const dateInput = ref<HTMLInputElement | null>(null)
const sliderEl = ref<HTMLElement | null>(null)

let fpInstance: flatpickr.Instance | null = null
let sliderInstance: SliderAPI | null = null

function parseFileSizeToMB(sizeString: string): number | null {
  if (!sizeString || sizeString.trim().toLowerCase() === 'n/a') return null
  const parts = sizeString.trim().split(/\s+/)
  if (parts.length < 2) return null
  const size = parseFloat(parts[0])
  const unit = parts[1].toUpperCase()
  if (isNaN(size)) return null
  if (unit.startsWith('TB')) return size * 1024 * 1024
  if (unit.startsWith('GB')) return size * 1024
  return size
}

function formatFileSize(mb: number): string {
  if (isNaN(mb)) return 'N/A'
  if (mb >= 1024 * 1024) return (mb / (1024 * 1024)).toFixed(2) + ' TB'
  if (mb >= 1024) return (mb / 1024).toFixed(2) + ' GB'
  return mb.toFixed(2) + ' MB'
}

const uniqueValues = (key: keyof BookResult) =>
  [...new Set(props.books.map(b => b[key] as string))].filter(v => v && v !== 'N/A').sort()

const languages = computed(() => uniqueValues('language'))
const bitrates = computed(() => uniqueValues('bitrate'))
const formats = computed(() => uniqueValues('format'))

const sizeRange = computed(() => {
  const sizes = props.books.map(b => parseFileSizeToMB(b.file_size)).filter((s): s is number => s !== null)
  if (sizes.length < 2) return null
  return { min: Math.min(...sizes), max: Math.max(...sizes) }
})

function parsePostDate(dateStr: string): Date | null {
  if (!dateStr || dateStr === 'N/A') return null
  const formatted = dateStr.replace(/(\d{1,2})\s(\w{3})\s(\d{4})/, '$2 $1, $3')
  const d = new Date(formatted)
  return isNaN(d.getTime()) ? null : d
}

function applyFilters() {
  const selectedDates = fpInstance?.selectedDates ?? []
  const raw = sliderInstance?.get()
  const sliderValues = raw ? (Array.isArray(raw) ? raw : [raw]).map(Number) : null

  const filtered = props.books.filter(book => {
    if (language.value && book.language !== language.value) return false
    if (bitrate.value && book.bitrate !== bitrate.value) return false
    if (format.value && book.format !== format.value) return false

    if (sliderValues) {
      const sizeMB = parseFileSizeToMB(book.file_size)
      if (sizeMB !== null && (sizeMB < sliderValues[0] || sizeMB > sliderValues[1])) return false
    }

    if (selectedDates.length === 2) {
      const bookDate = parsePostDate(book.post_date)
      if (!bookDate) return false
      bookDate.setHours(0, 0, 0, 0)
      if (bookDate < selectedDates[0] || bookDate > selectedDates[1]) return false
    }

    return true
  })

  emit('filtered', filtered)
}

function clearFilters() {
  language.value = ''
  bitrate.value = ''
  format.value = ''
  fpInstance?.clear()
  sliderInstance?.reset()
  emit('filtered', props.books)
}

function initFlatpickr() {
  if (!dateInput.value) return
  const dates = props.books.map(b => parsePostDate(b.post_date)).filter((d): d is Date => d !== null)
  const opts: flatpickr.Options.Options = { mode: 'range', dateFormat: 'Y-m-d' }
  if (dates.length > 0) {
    opts.minDate = new Date(Math.min(...dates.map(d => d.getTime())))
    opts.maxDate = new Date(Math.max(...dates.map(d => d.getTime())))
  }
  fpInstance = flatpickr(dateInput.value, opts)
}

function initSlider() {
  if (!sliderEl.value || !sizeRange.value) return
  const formatter = {
    to: (v: number) => formatFileSize(v),
    from: (v: string) => parseFloat(v),
  }
  sliderInstance = noUiSlider.create(sliderEl.value, {
    start: [sizeRange.value.min, sizeRange.value.max],
    connect: true,
    tooltips: [formatter, formatter],
    range: { min: sizeRange.value.min, max: sizeRange.value.max },
  })
}

watch(() => props.books, async () => {
  fpInstance?.destroy()
  sliderInstance?.destroy()
  fpInstance = null
  sliderInstance = null
  await nextTick()
  initFlatpickr()
  initSlider()
})

onMounted(() => {
  initFlatpickr()
  initSlider()
})

onBeforeUnmount(() => {
  fpInstance?.destroy()
  sliderInstance?.destroy()
})
</script>

<style scoped>
.filter-container {
    display: grid;
    gap: 1rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: rgba(255, 255, 255, 0.03);
    box-shadow: var(--shadow-sm);
}
.filter-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: end;
}
.filter-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
}
.filter-buttons {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    justify-content: flex-end;
}
select, input[type="text"] {
    min-height: 2.9rem;
    padding: 0.82rem 0.95rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.05);
    color: var(--text);
    outline: none;
    transition: border-color var(--transition), box-shadow var(--transition);
}
select:focus, input:focus {
    border-color: rgba(79, 140, 255, 0.7);
    box-shadow: 0 0 0 4px rgba(79, 140, 255, 0.18);
}
button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.9rem;
    min-width: 6rem;
    padding: 0.8rem 1.1rem;
    border-radius: var(--radius-md);
    background: linear-gradient(135deg, var(--accent), var(--accent-strong));
    color: var(--accent-contrast);
    font-weight: 700;
    transition: transform var(--transition), box-shadow var(--transition), filter var(--transition);
}
button:hover, button:focus-visible {
    transform: translateY(-1px);
    box-shadow: 0 18px 30px rgba(79, 140, 255, 0.22);
    filter: brightness(1.03);
}
.file-size-filter-wrapper {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
}
.file-size-filter-wrapper label {
    color: var(--text-muted);
    font-size: 0.9rem;
    font-weight: 600;
    white-space: nowrap;
}
.file-size-filter-wrapper > div {
    flex-grow: 1;
}

@media (max-width: 840px) {
    .filter-row {
        grid-template-columns: 1fr;
    }
    .filter-buttons {
        justify-content: stretch;
    }
    .filter-buttons button {
        width: 100%;
    }
}
</style>
