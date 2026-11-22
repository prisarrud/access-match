# Demo data

`properties.json` contains six fictional properties in Porto Alegre, Brazil. Each property includes the wording of its demo listing. The photos are synthetic. Design specifications describe the planned features, and inspection reports record measurements and observations from the stated visit date.

## Sources

| Property | Source | What the source says |
| --- | --- | --- |
| A · Edifício Ipê | [Listing](property-a/anuncio.md) | Says the entrance is step-free. |
| A · Edifício Ipê | [Front photo](property-a/entrada-frontal.jpg) | Shows a step between the sidewalk and the door landing. The photo leaves open whether another step-free entrance exists and how wide the photographed doorway is. |
| B · Residencial Oliveira | [Listing](property-b/anuncio.md) | Describes the entrance as having a “wide door.” |
| B · Residencial Oliveira | [Door photo](property-b/porta-entrada.jpg) and [landing photo](property-b/patamar-entrada.jpg) | Show the door and the area immediately around it. The start of the route from the sidewalk is outside the frame. |
| B · Residencial Oliveira | [Design specification](property-b/memorial-descritivo.pdf), p. 2, section 3.1 | Specifies an 85 cm clear opening for the lobby entrance door (PE-01) on April 18, 2023. |
| B · Residencial Oliveira | [Inspection report](property-b/ficha-vistoria.pdf), p. 2, section 3.1 | Records a measured clear opening of 78 cm for the same door (PE-01) on October 12, 2026. |
| C · Edifício Jacarandá | [Listing](property-c/anuncio.md), [entrance photo](property-c/entrada-principal.jpg) and [inspection report](property-c/ficha-vistoria.pdf), p. 1 | The inspection documents a continuous, step-free route from the sidewalk to the entrance door. |
| D · Residencial Manacá | [Listing](property-d/anuncio.md) and [ramp photo](property-d/rampa-parcial.jpg) | Show the upper part of the ramp. Its connection to the sidewalk remains to be confirmed. |
| E · Edifício Araucária | [Listing](property-e/anuncio.md), [door photo](property-e/porta-entrada.jpg) and [design specification](property-e/memorial-descritivo.pdf), p. 1 | The design specifies a 90 cm clear opening for the main entrance door. The current opening remains to be measured. |
| F · Residencial Cedro | [Listing](property-f/anuncio.md) and [entrance photo](property-f/entrada-principal.jpg) | The listing describes a step-free side entrance. The photo shows a step at the main entrance. |

## Add a property

Add an object to the `properties` array with a stable, unique `id`, the listing `title`, and its original `description`. The `photos` and `documents` arrays can be empty or omitted.

- Each photo has an `id`, a `path`, and `alt` text.
- Each document has an `id`, a `title`, a `type` (`memorial` or `vistoria`), and a `path`. If known, include the specification revision or inspection visit `date` in `YYYY-MM-DD` format.

Use paths relative to `data/demo` with `/` separators. Photo and document IDs must be unique within each property across both arrays. The property ID and source ID together identify the original file. The description belongs to the property. RAG associates each retrieved chunk with its PDF page.

## Validate the catalog

FastAPI loads and validates the catalog on startup, regardless of the working directory. A missing catalog starts empty. Invalid data or duplicate IDs produce an error with the catalog path and validation details.

Set up the Python environment using the [project README](../../README.md#getting-started---api), then run these commands from the repository root.

```bash
api/.venv/bin/python -c 'from api.app.properties.catalog import load_catalog; print(len(load_catalog().properties))'
api/.venv/bin/python -m unittest discover -s api/tests
```

<details>
<summary>Synthetic photo prompts</summary>

The photos were created with the integrated image generation tool. The Edifício Ipê photo was reused. The two Residencial Oliveira photos use an earlier synthetic image of the same property as a visual reference.

**edificio-ipe**

> Use case: photorealistic-natural. Generate one landscape smartphone real-estate listing photograph of the front pedestrian entrance to a fictional, unbranded brick and cream stucco apartment building in southern Brazil. From the public concrete sidewalk in ordinary overcast daylight, the camera looks slightly diagonally toward the closed glazed lobby door, with the sidewalk in the foreground. One clearly visible broad concrete step, with only one vertical riser, separates the sidewalk from the small landing right in front of this door. The step runs across the full visible approach to that door. The composition shows the front entrance and crops the sides of the building, so a different entrance could be outside the frame. Realistic residential scale and ground geometry. No visible ramp, people, signs, lettering, numbers, watermark, arrows, captions or collage.

**residencial-oliveira-foto-porta**

> Use case: photorealistic-natural. Use the reference as the exact fictional Residencial Oliveira building. Create one realistic landscape smartphone listing photograph taken from near the entrance, with the same charcoal-framed closed two-panel glazed lobby doorway, prominent central metal pull handle, charcoal gray stucco recess and pale tiled threshold. Straight-on view from the landing, close framing that shows the top, both jambs and the floor immediately at the door. Keep the door and real-estate materials consistent with the reference. Crop out the approach, ramp, sidewalk and street entirely. Natural overcast daylight. No people, ruler, numbers, signs, lettering, watermarks or collage.

**residencial-oliveira-foto-patamar**

> Use case: photorealistic-natural. Use the reference as the exact fictional Residencial Oliveira building. Create one realistic landscape smartphone listing photograph, taken at an oblique angle from near the top of the concrete approach and pointing toward the same closed two-panel charcoal-framed glazed lobby door. Keep the same charcoal stucco recess, pale tiled landing and gray metal handrail of the reference. Show the entire doorway, the landing, and only a short upper portion of the sloped concrete and rail in the foreground, cropped as they continue past the image edge. Keep the bottom of the incline, its connection to the sidewalk, the street and any alternate route fully out of view. Natural overcast daylight. No people, ruler, numbers, signs, lettering, watermarks or collage.

**Jacarandá, Manacá, Araucária and Cedro**

The integrated image generation tool used the following prompt for each property, with its name and scene substituted.

> Use case photorealistic-natural. One candid landscape 4:3 real estate listing photograph of the fictional {name} apartment building in Porto Alegre, Brazil. {scene}. Frame the base of the door, threshold, and all relevant visible floor details in the central lower half with generous side margins for horizontal card crops. Daylight, ordinary Brazilian residential architecture, realistic materials. No people, captions, signs, logos or text. Single photo, not a collage.

| Name | Scene |
| --- | --- |
| Jacarandá | light beige stucco, dark metal glass door, absolutely continuous level gray paved route from public sidewalk to flush threshold, no stairs or ramp, wide view with pavement foreground |
| Manacá | muted yellow facade, photograph close on a straight sloped concrete ramp with dark metal handrails leading to the landing and glass entrance door, lower starting point of ramp and the public sidewalk are outside the shot, visibly sloping ramp and top landing within frame |
| Araucária | blue gray facade, slightly angled view of closed wooden main entrance door, doorway and full stone threshold clearly visible with exterior pavement, no measuring devices or dimensions |
| Cedro | red brick facade, dark green main entrance door on a landing raised by exactly one distinct concrete step spanning the entry; show step nosing and sidewalk under it, side entrance outside shot |

</details>
