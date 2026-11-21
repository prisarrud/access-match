import { connection } from 'next/server'
import type { PropertySummary } from '../../types'

export async function loadProperties(): Promise<PropertySummary[] | null> {
  await connection()

  const baseUrl = process.env.API_BASE_URL

  if (!baseUrl) return null

  try {
    const url = new URL(`${baseUrl.replace(/\/$/, '')}/properties`)

    const response = await fetch(url, {
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    })

    if (!response.ok) return null

    const properties: PropertySummary[] = await response.json()
  
    return Array.isArray(properties) ? properties : null
  } catch {
    return null
  }
}
