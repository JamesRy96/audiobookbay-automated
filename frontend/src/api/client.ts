import type { BookResult, TorrentStatus, AppConfig, AppSettings } from '@/types'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(body.message || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function searchBooks(query: string): Promise<BookResult[]> {
  const data = await request<{ books: BookResult[] }>(
    `/api/search?q=${encodeURIComponent(query)}`
  )
  return data.books
}

export async function fetchStatus(): Promise<TorrentStatus[]> {
  const data = await request<{ torrents: TorrentStatus[] }>('/api/status')
  return data.torrents
}

export async function sendDownload(book: {
  link: string
  title: string
  author?: string
}): Promise<string> {
  const data = await request<{ message: string }>('/api/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(book),
  })
  return data.message
}

export async function fetchConfig(): Promise<AppConfig> {
  return request<AppConfig>('/api/config')
}

export async function fetchSettings(): Promise<AppSettings> {
  return request<AppSettings>('/api/settings')
}
