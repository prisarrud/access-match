import { selectionLimit } from '../../constants'

export function hasTwoPropertyIds(ids: string | string[] | undefined): ids is [string, string] {
  return Array.isArray(ids) && ids.length === selectionLimit && ids.every((id) => id.trim())
}
