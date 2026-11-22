import ui from '@/ui/shared.module.css'
import { loadProperties } from '../../services'
import { PropertySelection } from '../PropertySelection'

export async function PropertyCatalog() {
  const properties = await loadProperties()

  if (properties === null) {
    return (
      <p className={`${ui.container} ${ui.notice}`}>
        Não foi possível carregar o catálogo. Recarregue a página para tentar novamente.
      </p>
    )
  }

  if (properties.length === 0) {
    return <p className={`${ui.container} ${ui.notice}`}>O catálogo ainda não tem imóveis disponíveis.</p>
  }

  return <PropertySelection properties={properties} />
}
