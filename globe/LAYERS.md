# Rivers and wind on the globe

Both layers belong to the place you click. Each has its own button in the layer row, so you can hide one without hiding the other. The side panel still shows the wind phrase and the river summary when those buttons are off, so you can read the numbers without the drawing.

## Rivers

### Fetch

A click calls `fetchFlow` in `globe/web/src/api.ts`.

1. If the globe API answers, the browser requests `GET /flow?lat=&lon=`.
2. `globe/api/rivers.py` asks the public MERIT river-runner for the downstream line from that point. No API key.
3. Names MERIT leaves blank are filled from OpenStreetMap waterways that lie on the path (Overpass). A name is kept only when it sits within about 2.5 km of the line.
4. The path is thinned to points at least 1.2 km apart, capped around 420 points. Up to six names are kept, spaced along the line, and snapped onto the thinned path so the label sits on the stroke.
5. The API remembers a result for a point rounded to 0.001 degrees. A miss is not cached.
6. If the API is down, the browser asks MERIT directly and skips the OpenStreetMap names.

### Render

`globe/web/src/Earth.tsx` draws the line only when the Rivers button is on and the path has at least two points.

- The stroke is a Cesium polyline at 1,200 m, width 4, glow color `#9ad7ff`.
- Each name is a white label at 1,400 m on that line.

### Update

The path is fetched again only when you click a new place. Changing the scene date, playing the 12 days, or turning other layers on does not refetch it. Turning Rivers off removes the line and the labels. Turning it back on uses the path already loaded for that click.

## Wind

### Fetch

`fetchWind` in `globe/web/src/wind.ts` asks Open-Meteo. No API key. It samples a 3 by 3 grid: the corners, the edge midpoints, and the center of the study box (about 5 km). Before the box arrives it uses a small box around the click.

- A date on or before today uses the archive API: that day's maximum 10 m wind speed and the dominant direction, in km/h.
- If that day is empty, or the date is in the future, it uses the forecast API's current 10 m wind. The label then starts with `now`.
- `cleanArrows` drops a sample whose speed is missing, negative, or above 250 km/h, or whose direction is not a number. Direction is wrapped into 0–360.
- The side-panel phrase is the sample nearest the click. The credit is Open-Meteo.

A network or parse failure returns nothing. The panel then shows an ellipsis, and no arrows are drawn.

### Render

When the Wind button is on, each kept sample is a pale arrow billboard, 22 by 30 pixels, rotated to the direction the wind blows toward (the source direction plus 180 degrees). The arrow sits near 700 m and drifts a short step along that bearing on a six-second loop. The arrows are not a speed-colored field.

### Update

Wind is fetched again when the place changes or the scene date changes, including each step of playback. The new field replaces the old one. There is no blend between days. Turning Wind off hides the arrows and leaves the river line, the risk colors, and the panel phrase in place.

## Checking and cleaning the wind layer

1. Open a site and turn Wind on. You should see up to nine arrows on the study box. The panel Wind line should match the arrow nearest the pin, for example `18 km/h from the northwest`. Under 1 km/h the phrase is `calm`.
2. In the browser network list, a past date should call `archive-api.open-meteo.com` with nine latitudes and nine longitudes. A label that starts with `now` means that archive day was empty and the arrows are live wind, not the scene date. Pick another date, or reload, if you need the day you selected.
3. Do not treat nine identical arrows as a stuck layer. The box is about 5 km, and Open-Meteo often returns one value for the whole box.
4. There is no wind file to edit. Bad samples are already dropped by `cleanArrows` before anything is drawn. To clear the picture, turn Wind off. To fetch again, change the date or click the place again.
5. Wind does not move the river path, and the river path does not filter the wind.

## Other layer buttons

Each button switches only its own layer. Closing the study panel does not turn them off. Opening a site does not turn Clouds on.

| Button | What it draws | Default |
| --- | --- | --- |
| Blue Marble / OpenStreetMap | The base picture. One of the two is always on. | Blue Marble |
| Clouds | NASA GIBS MODIS Terra true color for 13, 14, and 15 October 2026, stacked so a black orbit gap shows an earlier day instead of the ocean. | Off |
| Fires | MODIS Terra thermal anomalies for 15 October 2026. | Off |
| Soil moisture | SMAP L4 surface soil moisture for 16 May 2026. | Off |
| Satellites | Illustrated NISAR orbit, about 747 km up, on a 12-day repeat. Not a live feed. | On |
| Wind | The Open-Meteo arrows above. | On |
| Rivers | The downstream path and names above. | On |
| Risk colors | The study-box outline and the green-to-red runoff colors. The camera still frames the box when this is off. | On |

Site pins stay on. They are how you jump to a place, not a data layer.
