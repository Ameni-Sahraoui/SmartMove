# Third-party notices

## Plotly.js

`web/vendor/plotly.min.js` is locally bundled Plotly.js (version stated in its header). Plotly.js is distributed under the MIT license by Plotly, Inc. The bundle retains its embedded license notices. See `docs/licenses/Plotly_LICENSE.txt` for the package MIT notice; transitive component notices embedded in the distribution remain intact. No font files are redistributed.

## Natural Earth

The low-resolution Canada and United States outlines in `web/assets/map-shapes.json` are derived from the Natural Earth low-resolution dataset distributed with the installed pyogrio test fixture. Geometry was simplified/projected into a schematic SVG coordinate space. Natural Earth data is public domain. Terms: https://www.naturalearthdata.com/about/terms-of-use/ . Geographic boundaries are a visual reference, not legal or navigational guidance.

## Visual reference

The mountain background crops are derived from the AI-generated dashboard image supplied in this conversation. Only decorative scenery crops are embedded; dashboard panels, numbers, map interaction and charts are implemented as web components, not copied into one flattened screenshot.

## Runtime packages

Python libraries are installed by pip from the pinned requirements, rather than distributed as binary environment files. Their respective licenses apply. C#/.NET and SQL Server are optional integration technologies, not bundled runtimes. No credentials, proprietary font binaries, maps requiring a paid token, or production API secrets are included.
