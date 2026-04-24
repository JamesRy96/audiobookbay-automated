export interface BookResult {
  title: string
  author: string | null
  link: string
  cover: string
  language: string
  post_date: string
  format: string
  bitrate: string
  file_size: string
}

export interface TorrentStatus {
  name: string
  progress: number
  state: string
  size: string
}

export interface AppConfig {
  nav_link_name: string | null
  nav_link_url: string | null
}

export interface AppSettings {
  [key: string]: string | number | boolean | null
}
