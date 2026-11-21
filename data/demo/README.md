# Dados da demonstração

`properties.json` contém dois imóveis fictícios de Porto Alegre (RS). Cada imóvel preserva a descrição original do anúncio. As fotos são sintéticas, os memoriais registram previsões de projeto e as vistorias registram observações e medições feitas na data indicada.

## Onde conferir as fontes

| Imóvel | Fonte | O que consta na fonte |
| --- | --- | --- |
| A · Edifício Ipê | [Anúncio](property-a/anuncio.md) | Afirma que a entrada é sem degraus. |
| A · Edifício Ipê | [Foto frontal](property-a/entrada-frontal.jpg) | Mostra um degrau entre a calçada e o patamar da porta fotografada. A existência de outro acesso sem degraus e a largura livre da porta ficam em aberto. |
| B · Residencial Oliveira | [Anúncio](property-b/anuncio.md) | Descreve a entrada apenas como tendo uma «porta ampla». |
| B · Residencial Oliveira | [Foto da porta](property-b/porta-entrada.jpg) e [foto do patamar](property-b/patamar-entrada.jpg) | Mostram a porta e seu entorno imediato. O início do percurso desde a calçada fica fora do quadro. |
| B · Residencial Oliveira | [Memorial descritivo](property-b/memorial-descritivo.pdf), p. 2, seção 3.1 | Prevê 85 cm de vão livre para a porta de entrada do hall (PE-01) em 18/04/2023. |
| B · Residencial Oliveira | [Ficha de vistoria](property-b/ficha-vistoria.pdf), p. 2, seção 3.1 | Registra 78 cm de vão livre medidos na mesma porta (PE-01) em 12/10/2026. |

## Como acrescentar um imóvel

Acrescente um objeto à lista `properties` com um `id` estável e único, o `title` do anúncio e a `description` copiada do texto original. As listas `photos` e `documents` podem ser vazias ou omitidas.

- Cada foto tem `id`, `path` e `alt` (texto alternativo).
- Cada documento tem `id`, `title`, `type` (`memorial` ou `vistoria`) e `path`. Quando conhecida, informe a `date` da revisão do memorial ou da visita de vistoria no formato `AAAA-MM-DD`.

Use caminhos relativos a `data/demo`, com barras `/`. Os IDs de fotos e documentos precisam ser únicos dentro do imóvel, inclusive entre as duas listas. O par de IDs do imóvel e da fonte permite identificar o arquivo original. A descrição pertence ao próprio imóvel. A página será associada ao trecho recuperado pelo RAG.

## Como validar

O FastAPI lê e valida o catálogo na inicialização, independentemente do diretório de execução. Se o arquivo estiver ausente, o catálogo começa vazio. Formato inválido e IDs duplicados geram um erro com o caminho do catálogo e o detalhe da validação.

Configure o ambiente virtual conforme o [README do projeto](../../README.md#getting-started---api). Depois, execute os comandos abaixo na raiz do repositório.

```bash
api/.venv/bin/python -c 'from api.app.properties.catalog import load_catalog; print(len(load_catalog().properties))'
api/.venv/bin/python -m unittest discover -s api/tests
```

<details>
<summary>Prompts das fotos sintéticas</summary>

As fotos foram geradas com a ferramenta integrada de geração de imagens. A foto do Edifício Ipê foi reaproveitada. As duas fotos do Residencial Oliveira usam uma imagem sintética anterior do mesmo imóvel como referência visual.

**edificio-ipe**

> Use case: photorealistic-natural. Generate one landscape smartphone real-estate listing photograph of the front pedestrian entrance to a fictional, unbranded brick and cream stucco apartment building in southern Brazil. From the public concrete sidewalk in ordinary overcast daylight, the camera looks slightly diagonally toward the closed glazed lobby door, with the sidewalk in the foreground. One clearly visible broad concrete step, with only one vertical riser, separates the sidewalk from the small landing right in front of this door. The step runs across the full visible approach to that door. The composition shows the front entrance and crops the sides of the building, so a different entrance could be outside the frame. Realistic residential scale and ground geometry. No visible ramp, people, signs, lettering, numbers, watermark, arrows, captions or collage.

**residencial-oliveira-foto-porta**

> Use case: photorealistic-natural. Use the reference as the exact fictional Residencial Oliveira building. Create one realistic landscape smartphone listing photograph taken from near the entrance, with the same charcoal-framed closed two-panel glazed lobby doorway, prominent central metal pull handle, charcoal gray stucco recess and pale tiled threshold. Straight-on view from the landing, close framing that shows the top, both jambs and the floor immediately at the door. Keep the door and real-estate materials consistent with the reference. Crop out the approach, ramp, sidewalk and street entirely. Natural overcast daylight. No people, ruler, numbers, signs, lettering, watermarks or collage.

**residencial-oliveira-foto-patamar**

> Use case: photorealistic-natural. Use the reference as the exact fictional Residencial Oliveira building. Create one realistic landscape smartphone listing photograph, taken at an oblique angle from near the top of the concrete approach and pointing toward the same closed two-panel charcoal-framed glazed lobby door. Keep the same charcoal stucco recess, pale tiled landing and gray metal handrail of the reference. Show the entire doorway, the landing, and only a short upper portion of the sloped concrete and rail in the foreground, cropped as they continue past the image edge. Keep the bottom of the incline, its connection to the sidewalk, the street and any alternate route fully out of view. Natural overcast daylight. No people, ruler, numbers, signs, lettering, watermarks or collage.

</details>
