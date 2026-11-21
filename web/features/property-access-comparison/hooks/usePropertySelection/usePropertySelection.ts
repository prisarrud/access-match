import { useState } from 'react'
import { selectionLimit } from '../../constants'

export function usePropertySelection() {
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  function toggleProperty(id: string) {
    setSelectedIds((current) => {
      if (current.includes(id)) {
        return current.filter((selected) => selected !== id)
      }
      return current.length < selectionLimit ? [...current, id] : current
    })
  }

  return { selectedIds, toggleProperty }
}
