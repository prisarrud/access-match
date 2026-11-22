export type PropertySummary = {
  id: string
  title: string
  description: string
  cover: { url: string, alt: string } | null
  photos: { id: string, alt: string, url: string | null }[]
  documents: { id: string, title: string, url: string | null }[]
}
