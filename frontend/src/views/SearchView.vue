<template>
  <div class="title-container">
    <h1>Search AudiobookBay</h1>
  </div>

  <div class="search-container">
    <form class="search-form" @submit.prevent="doSearch">
      <input
        v-model="query"
        type="text"
        placeholder="Enter book name"
        class="search-bar"
        required
      />
      <button type="submit" class="search-button" :disabled="loading">
        <span class="button-text">Search</span>
        <span v-if="loading" class="button-spinner"><span class="spinner"></span></span>
      </button>
      <button
        v-if="allBooks.length > 0"
        type="button"
        class="new-search-button"
        @click="newSearch"
      >New Search</button>
    </form>
  </div>

  <div v-if="scrollingMessage" class="message-scroller">
    <p>{{ scrollingMessage }}</p>
  </div>

  <p v-if="error" class="error-message">{{ error }}</p>

  <FilterBar
    v-if="allBooks.length > 0"
    :books="allBooks"
    @filtered="visibleBooks = $event"
  />

  <table v-if="visibleBooks.length > 0">
    <tbody>
      <tr v-for="book in visibleBooks" :key="book.link">
        <td><img :src="book.cover" alt="Cover Art" class="cover" width="100" /></td>
        <td>
          <p class="book-title">{{ book.title }}</p>
          <div class="property-results-container">
            <span>Language: {{ book.language }}</span>
            <span>Bitrate: {{ book.bitrate }}</span>
            <span>Format: {{ book.format }}</span>
            <span>File Size: {{ book.file_size }}</span>
            <span>Posted: {{ book.post_date }}</span>
          </div>
        </td>
        <td class="actions">
          <button @click="openDetails(book.link)">Details</button>
          <button @click="download(book)" :disabled="downloading === book.link">
            {{ downloading === book.link ? 'Sending...' : 'Download to Server' }}
          </button>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue'
import type { BookResult } from '@/types'
import { searchBooks, sendDownload } from '@/api/client'
import FilterBar from '@/components/FilterBar.vue'

const query = ref('')
const allBooks = ref<BookResult[]>([])
const visibleBooks = ref<BookResult[]>([])
const loading = ref(false)
const error = ref('')
const downloading = ref<string | null>(null)
const scrollingMessage = ref('')

const messages = [
  "Searching... This better be worth it!",
  "Hold on, this takes a while...",
  "Still searching... Maybe grab a snack?",
  "Patience, young grasshopper...",
  "Wow, this is taking a minute!",
  "Don't worry, I got this!",
  "Maybe go for a walk?",
  "Still thinking... Almost there!",
  "Finding the best results for you!",
  "Hang tight! Searching magic happening!",
  "One moment... while I consult the ancients.",
  "Beep boop... processing... please wait...",
  "My hamsters are running on a wheel, almost there!",
  "Just gathering some pixie dust, be right back!",
  "Is it lunchtime yet? Oh, searching... right.",
  "Please remain calm, the search is in progress.",
  "Warning: Search may cause extreme awesomeness.",
  "Calculating the optimal route to your results...",
  "Almost there... just defragmenting my brain.",
  "Searching... because the internet is a big place!",
  "Polishing the search results for your viewing pleasure.",
  "The search is strong with this one.",
  "Please wait while I summon the search demons.",
  "Searching in hyperspace... almost there!",
  "My coffee is kicking in... search commencing!",
  "Just a few more gigabytes to process...",
  "Rome wasn't built in a day.",
  "Don't blame me, the internet is slow today.",
  "Almost there... just need to find the right key...",
]

let messageTimer: ReturnType<typeof setTimeout> | null = null
let messageInterval: ReturnType<typeof setInterval> | null = null

function startMessages() {
  messageTimer = setTimeout(() => {
    const shuffled = [...messages].sort(() => Math.random() - 0.5)
    let idx = 0
    scrollingMessage.value = shuffled[idx]
    messageInterval = setInterval(() => {
      idx = (idx + 1) % shuffled.length
      scrollingMessage.value = shuffled[idx]
    }, 5000)
  }, 5000)
}

function stopMessages() {
  if (messageTimer) { clearTimeout(messageTimer); messageTimer = null }
  if (messageInterval) { clearInterval(messageInterval); messageInterval = null }
  scrollingMessage.value = ''
}

async function doSearch() {
  if (!query.value.trim()) return
  loading.value = true
  error.value = ''
  allBooks.value = []
  visibleBooks.value = []
  startMessages()

  try {
    const books = await searchBooks(query.value.trim())
    allBooks.value = books
    visibleBooks.value = books
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Search failed'
  } finally {
    loading.value = false
    stopMessages()
  }
}

function openDetails(link: string) {
  window.open(link, '_blank')
}

async function download(book: BookResult) {
  downloading.value = book.link
  try {
    const message = await sendDownload({
      link: book.link,
      title: book.title,
      author: book.author ?? undefined,
    })
    alert(message)
  } catch (e) {
    alert(e instanceof Error ? e.message : 'Download failed')
  } finally {
    downloading.value = null
  }
}

function newSearch() {
  query.value = ''
  allBooks.value = []
  visibleBooks.value = []
  error.value = ''
  stopMessages()
}

onBeforeUnmount(() => stopMessages())
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
.search-container {
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: rgba(255, 255, 255, 0.03);
    box-shadow: var(--shadow-sm);
    margin-bottom: 0.5rem;
}
.search-form {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 0.75rem;
}
.search-bar {
    width: 100%;
    min-height: 3.2rem;
    padding: 0.82rem 0.95rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text);
    font-size: 1rem;
    outline: none;
    transition: border-color var(--transition), box-shadow var(--transition);
}
.search-bar::placeholder { color: var(--text-subtle); }
.search-bar:focus {
    border-color: rgba(79, 140, 255, 0.7);
    box-shadow: 0 0 0 4px rgba(79, 140, 255, 0.18);
    background: rgba(255, 255, 255, 0.06);
}
.search-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 2.9rem;
    padding: 0.8rem 1.1rem;
    border-radius: var(--radius-md);
    background: linear-gradient(135deg, var(--accent), var(--accent-strong));
    color: var(--accent-contrast);
    font-weight: 700;
    white-space: nowrap;
    transition: transform var(--transition), box-shadow var(--transition), filter var(--transition);
}
.search-button:hover:not(:disabled), .search-button:focus-visible {
    transform: translateY(-1px);
    box-shadow: 0 18px 30px rgba(79, 140, 255, 0.22);
    filter: brightness(1.03);
}
.search-button:disabled { opacity: 0.7; cursor: wait; }
.new-search-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.9rem;
    padding: 0.8rem 1.1rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-strong);
    background: transparent;
    color: var(--text-muted);
    font-weight: 700;
    white-space: nowrap;
    transition: transform var(--transition), border-color var(--transition), color var(--transition);
}
.new-search-button:hover {
    transform: translateY(-1px);
    border-color: var(--accent);
    color: var(--text);
}
.button-spinner { margin-left: 0.15rem; }
.spinner {
    display: inline-block;
    width: 1rem;
    height: 1rem;
    border: 0.16rem solid rgba(255, 255, 255, 0.14);
    border-top-color: var(--accent-contrast);
    border-radius: 50%;
    animation: spin 0.9s linear infinite;
}
.message-scroller {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: rgba(255, 255, 255, 0.03);
    box-shadow: var(--shadow-sm);
    width: fit-content;
    max-width: 100%;
    padding: 0.85rem 1rem;
}
.message-scroller p { margin: 0; color: var(--text-muted); }
.error-message {
    margin: 0;
    padding: 0.85rem 1rem;
    border: 1px solid rgba(248, 113, 113, 0.3);
    border-radius: var(--radius-md);
    background: rgba(248, 113, 113, 0.08);
    color: #ffb5b5;
    font-weight: 600;
}
table {
    width: 100%;
    border-collapse: collapse;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    background: var(--surface-strong);
    box-shadow: var(--shadow-md);
}
td {
    padding: 0.95rem 1rem;
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid rgba(160, 177, 214, 0.12);
}
tr:hover td { background: rgba(255, 255, 255, 0.025); }
img.cover {
    width: clamp(72px, 12vw, 110px);
    aspect-ratio: 2 / 3;
    object-fit: cover;
    border-radius: 0.7rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: var(--shadow-sm);
}
.book-title {
    margin: 0 0 0.55rem;
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.35;
    color: var(--text);
}
.property-results-container {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem 0.65rem;
    color: var(--text-muted);
    font-size: 0.82rem;
    margin-bottom: 0.3rem;
}
.property-results-container span {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
}
.property-results-container span:not(:last-child)::after {
    content: "\2022";
    margin-left: 0.65rem;
    color: var(--text-subtle);
}
.actions { white-space: nowrap; }
.actions button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 2.9rem;
    padding: 0.8rem 1.1rem;
    margin-right: 0.5rem;
    border-radius: var(--radius-md);
    background: linear-gradient(135deg, var(--accent), var(--accent-strong));
    color: var(--accent-contrast);
    font-weight: 700;
    transition: transform var(--transition), box-shadow var(--transition), filter var(--transition);
}
.actions button:hover:not(:disabled), .actions button:focus-visible {
    transform: translateY(-1px);
    box-shadow: 0 18px 30px rgba(79, 140, 255, 0.22);
    filter: brightness(1.03);
}
.actions button:disabled { opacity: 0.7; cursor: wait; }

@media (max-width: 840px) {
    .search-form { grid-template-columns: 1fr; }
    .search-button, .new-search-button { width: 100%; }
    .actions { white-space: normal; }
    .actions button { width: 100%; margin: 0 0 0.5rem; }
}
@media (max-width: 560px) {
    .title-container h1 { max-width: none; }
    .property-results-container span:not(:last-child)::after { content: ""; margin-left: 0; }
    table, th, td { font-size: 0.92rem; }
}
</style>
