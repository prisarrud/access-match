# Dados da demonstração

`properties.json` contém dois imóveis fictícios de Porto Alegre (RS). Cada imóvel preserva a descrição original do anúncio. As fotos são sintéticas, os memoriais registram previsões de projeto e as vistorias registram observações e medições feitas na data indicada.

No Edifício Ipê, a vistoria registra um degrau na entrada frontal e deixa o acesso lateral em aberto. No Residencial Oliveira, a vistoria registra uma rampa e mede 82 cm de passagem livre na porta, diante dos 90 cm previstos no memorial. As informações se restringem ao percurso entre a calçada e a porta de entrada.

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

As duas imagens foram geradas com a ferramenta integrada de geração de imagens.

**edificio-ipe**

> Use case: photorealistic-natural. Generate one landscape smartphone real-estate listing photograph of the front pedestrian entrance to a fictional, unbranded brick and cream stucco apartment building in southern Brazil. From the public concrete sidewalk in ordinary overcast daylight, the camera looks slightly diagonally toward the closed glazed lobby door, with the sidewalk in the foreground. One clearly visible broad concrete step, with only one vertical riser, separates the sidewalk from the small landing right in front of this door. The step runs across the full visible approach to that door. The composition shows the front entrance and crops the sides of the building, so a different entrance could be outside the frame. Realistic residential scale and ground geometry. No visible ramp, people, signs, lettering, numbers, watermark, arrows, captions or collage.

**residencial-oliveira**

> Use case: photorealistic-natural. Generate one landscape smartphone real-estate listing photograph of the pedestrian entrance to a fictional gray and off-white low-rise apartment building in southern Brazil. Ordinary overcast daylight, camera looking diagonally from the public concrete sidewalk toward a closed dark framed glazed lobby door. Show the full continuous path from the sidewalk up a gently inclined single straight concrete pedestrian ramp, then over a small level landing directly to the lobby door. A simple metal handrail along one edge of the slope makes the ramp legible. Keep the public sidewalk, bottom of the ramp, top landing and doorway in the same frame. No stairs or abrupt riser along the visible path. Realistic residential scale and ground geometry. No people, signs, lettering, numbers, watermark, arrows, captions or collage.

</details>
