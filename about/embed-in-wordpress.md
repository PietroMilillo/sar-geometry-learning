# Embedding in the WordPress site

For whoever builds the **Learning / SAR Geometry** page on
<https://milillo.cive.uh.edu>.

The exercises are static pages on GitHub Pages. Do **not** copy the files into
WordPress — the media library will fight the 200-odd images and the relative
paths. Link or iframe instead.

## Option A — link out (simplest, recommended)

Two buttons on the Learning page. Full window, no iframe scrolling problems,
works on phones.

```html
<p><a class="button" href="https://pietromilillo.github.io/sar-geometry-learning/look-angle/"
      target="_blank" rel="noopener">Exercise 1 — Look Angle</a></p>
<p><a class="button" href="https://pietromilillo.github.io/sar-geometry-learning/where-the-summit-lands/"
      target="_blank" rel="noopener">Exercise 2 — Where the Summit Lands</a></p>
```

## Option B — embed in the page

Exercise 2 needs height; below about 700 px it gets cramped.

```html
<iframe src="https://pietromilillo.github.io/sar-geometry-learning/where-the-summit-lands/"
        style="width:100%;height:1400px;border:1px solid #ccc;border-radius:8px"
        loading="lazy" title="Where the Summit Lands — SAR geometric distortion">
</iframe>
```

In the block editor use a **Custom HTML** block. The Classic editor strips
iframes unless you are an administrator — if the iframe vanishes on save, that
is why, and Option A avoids it.

## Notes

- GitHub Pages serves HTTPS, so there is no mixed-content warning.
- Nothing is tracked. There is no server behind these pages and no analytics.
- The landing page at the repository root already sequences both exercises with
  learning objectives, so you may prefer to link to it alone:
  <https://pietromilillo.github.io/sar-geometry-learning/>
- If the URL should live under `milillo.cive.uh.edu` instead, GitHub Pages
  supports a custom domain (Settings → Pages → Custom domain) — that needs a DNS
  CNAME the UH web team would have to add.
