# brand ticker

one number. every logo you have bothered.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/auraseb/auraseb/main/ticker/dark.svg">
  <img alt="the live ticker on github.com/auraseb" src="https://raw.githubusercontent.com/auraseb/auraseb/main/ticker/light.svg" width="100%">
</picture>

your contributions in the last year, set edge to edge. under it, a slow line of the marks of every org you have opened a pull request or an issue in. light and dark, pure svg, so it survives github's image proxy. it refreshes itself.

## use

put this in `.github/workflows/ticker.yml` of your `you/you` profile repo:

```yaml
name: ticker
on: { schedule: [{ cron: "0 */6 * * *" }], workflow_dispatch: {} }
permissions: { contents: write }
jobs:
  ticker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: auraseb/brand-ticker@v1
        with: { min_stars: 100 }
```

run it once from the actions tab. then put this in your readme:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="ticker/dark.svg">
  <img alt="contributions" src="ticker/light.svg" width="100%">
</picture>
```

## inputs

| input | default | what it does |
| --- | --- | --- |
| `user` | the repo owner | whose ticker |
| `mode` | `prs_and_issues` | or `merged_prs`, to count only what landed |
| `min_stars` | `100` | repos with fewer stars do not count |
| `exclude_orgs` | | logins to leave out, comma separated |
| `first` | | logins to lead the strip, comma separated |
| `max_logos` | `30` | the strip stops here |
| `light_ink` | `#191A1C` | the one colour, light mode |
| `dark_ink` | `#F0F3F6` | the one colour, dark mode |
| `light_bg` | `none` | ground in light mode. none is see through |
| `dark_bg` | `none` | ground in dark mode |
| `output_dir` | `ticker` | where `light.svg` and `dark.svg` go |
| `commit` | `true` | commit and push them when they change |
| `token` | `github.token` | reads public search and avatars. nothing else |

outputs: `contributions` and `orgs`.

## how

the number is the one on your profile, set in your system font and stretched with `textLength`, so it always runs the full width.

orgs come from github search: orgs only, public repos only, biggest names first. a brand in the bundled set gets its vector mark. everything else is keyed out of the org's avatar: the ground goes, the mark stays, in one ink. avatars that are photos, gradients or line art too fine to read are left out instead of smudged. hand tuned exceptions live in `brand_ticker/data/overrides.json`.

the strip moves at 24 pixels a second and stops for reduced motion.

vector marks from [simple icons](https://simpleicons.org), cc0.

mit.
