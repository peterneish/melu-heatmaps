# MELU collectors heatmaps

Heatmaps of the top collectors at the University of Melbourne Herbarium (MELU, ALA data resource `dr13282`),
by genus and by decade. Every collector, column heading and cell links to the matching search on the Atlas of Living Australia.

## Rebuild the data and page

    pip install -r requirements.txt
    ./build.sh

This runs `clean_names.py` (genus matrix, with collector name cleanup), `collector_years.py` (decade matrix) and
`combine.py`, which writes `docs/index.html`. The first run makes a few hundred API calls; later runs reuse the local caches.
Edit `ALIASES` in `clean_names.py` to merge collector name variants.

`docs/index.html` is fully self-contained (data embedded, no build step on the server), so you can also open it directly in a browser.

## Publish on GitHub Pages

1. Push this repo to GitHub.
2. Settings > Pages > Build and deployment > Deploy from a branch.
3. Choose branch `main` and folder `/docs`, then Save.
4. The site appears at `https://<your-username>.github.io/<repo-name>/`.

Data: University of Melbourne Herbarium via the Atlas of Living Australia.
