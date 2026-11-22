import { useState, useSyncExternalStore } from 'react'
import { selectionLimit } from '../../constants'

const subscribe = () => () => {}

export function usePropertySelection() {
  const isReady = useSyncExternalStore(subscribe, () => true, () => false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  function toggleProperty(id: string) {
    setSelectedIds((current) => {
      if (current.includes(id)) {
        return current.filter((selected) => selected !== id)
      }
      return current.length < selectionLimit ? [...current, id] : current
    })
  }

  return { isReady, selectedIds, toggleProperty }
}
