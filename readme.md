[Showcase scores](https://twitter.com/bmenrigh_pogo/status/1680851346768150528?s=20)

[New Size System](https://twitter.com/bmenrigh_pogo/status/1618456354712350720?s=20)

## Building the standalone probability app

The finished app is `pvalue_lookup.html`. It is a single, self-contained HTML
file: Pokémon statistics, float32 display-extrema notes, polynomial CDF tables,
CSS, and JavaScript are all embedded during the build. It can be opened
directly without a web server and makes no network requests.

The normal refresh-and-build workflow is:

1. obtain a current Game Master in JSON format;
2. extract and validate `pokemon_stats.tsv`;
3. review the float32 display-extrema report;
4. build `pvalue_lookup.html`; and
5. run the tests.

The app builder requires Python 3 and the existing compressed distributions in
`cdfs_poly/`. NumPy is needed only to regenerate those polynomial CDF files,
as described under [Polynomial CDF compression](#polynomial-cdf-compression).

### 1. Get a current JSON Game Master

Download or export a new, complete Pokémon GO Game Master from a trusted
source and save it as `GAME_MASTER.json` in the repository root. The extractor
expects decoded JSON whose top level is an array of Game Master template
objects, not protobuf data or a partial list containing only ordinary Pokémon
settings. The extended Pokémon settings and temporary-evolution overrides are
needed for size bounds and forms such as Primal Groudon and Primal Kyogre.

The build tools do not download the Game Master automatically. The source JSON
also does not provide a reliable upstream snapshot date or version, so the
date embedded in the finished page records when the app was built.

### 2. Extract the Pokémon statistics

Run:

```console
$ ./read_pokemon_stats_from_gm.py GAME_MASTER.json > pokemon_stats.tsv
```

The TSV written to standard output contains Pokédex number, form name, mean
height, mean weight, XXS class, and XXL class. Progress and validation warnings
are written to standard error, so they remain visible when the table is
redirected.

Review every warning when updating the Game Master. Records with missing,
contradictory, or unsupported settings are omitted instead of being guessed.
Zorua, Pumpkaboo, and Gourgeist are intentionally omitted, as are forms whose
Pokédex means conflict with their size bounds. Use `--strict` when a nonzero
exit status is desired for any validation warning:

```console
$ ./read_pokemon_stats_from_gm.py --strict GAME_MASTER.json \
    > pokemon_stats.tsv
```

The supported class definitions are XXS minima of `0.49` and `0.25`, and XXL
maxima of `1.55`, `1.75`, and `2.00`. If a future Game Master introduces
another class, the extractor and the distribution set must be updated rather
than silently assigning it to an existing class.

### Audit evolutions that change XXL height class

To produce a TSV containing every direct evolution whose source and target
have different XXL height classes, run:

```console
$ ./list_xxl_class_changing_evolutions.py GAME_MASTER.json \
    > xxl_class_changing_evolutions.tsv
```

Each row includes the source and target Pokédex numbers, form names, mean
heights, mean weights, XXL classes, and class-change direction. The script
reads both `evolutionBranch` and `evolutionIds`, resolves `_NORMAL` and
collapsed `_ALL` forms, and removes duplicate representations of the same
evolution. Validation and unresolved-form warnings go to standard error;
`--strict` makes any warning produce an unsuccessful exit status.

Zorua is included because its Game Master XXL class can still be useful for
an evolution audit even though Zorua is omitted from the probability app.
Pumpkaboo and Gourgeist are ignored entirely: their special form-size system
does not use the ordinary XXL height classes modeled by this report.

### 3. Audit float32 display extrema

Generate the human-readable report with:

```console
$ ./check_float32_display_extrema.py pokemon_stats.tsv \
    > float32_display_extrema.txt
```

This reports theoretical minimum-height, maximum-height, and maximum-weight
display boundaries whose two-decimal rounding changes after conversion to
IEEE-754 float32. Review the report when the stats change. It is an audit
artifact and is not an input to the next command: the app builder runs the
same extrema calculation directly from `pokemon_stats.tsv` and embeds the
affected rows automatically.

### 4. Build the standalone HTML

With the default filenames and directories, run:

```console
$ ./build_pvalue_webapp.py
```

This reads:

- `pokemon_stats.tsv`;
- the 12 compressed CDF files in `cdfs_poly/`; and
- `pvalue_webapp_template.html`.

It writes `pvalue_lookup.html` and prints the number of embedded Pokémon,
polynomial segments, and output bytes to standard error. The current local
date is embedded as the page's build date. The builder also verifies the stats,
compressed-CDF format, contiguous polynomial ranges, and template markers
before writing the page.

Alternative locations can be supplied explicitly:

```console
$ ./build_pvalue_webapp.py \
    --stats pokemon_stats.tsv \
    --cdfs cdfs_poly \
    --template pvalue_webapp_template.html \
    --output pvalue_lookup.html
```

The distributions in `cdfs_poly/` are normalized and species-independent, so
adding ordinary Pokémon or forms normally requires only a new stats extraction
and HTML build. Regenerate the CDFs when the modeled generation algorithm,
class distributions, numerical convolution, or compression settings change.

### 5. Verify the build

Run the app, stats-extractor, and float32-extrema tests:

```console
$ python3 -m unittest -q \
    test_build_pvalue_webapp.py \
    test_check_float32_display_extrema.py \
    test_read_pokemon_stats_from_gm.py
```

After the tests pass, open `pvalue_lookup.html` directly and check both light
and dark themes, a height lookup, a weight lookup, Displayed and Exact input
modes, and both tail directions.

## Weighted size-class PDFs

`pdf_tools/weighted_average_pdfs.py` accepts alternating `n/m` weights and PDF
paths. It normalizes each left-edge-aligned PDF to its assigned weight and
writes their weighted average to standard output:

```console
$ ./pdf_tools/weighted_average_pdfs.py \
    1/250  six_figs_raw/xxs_pdf.txt \
    1/40   six_figs_raw/xs_pdf.txt \
    471/500 six_figs_raw/avg_pdf.txt \
    1/40   six_figs_raw/xl_pdf.txt \
    1/250  six_figs_raw/xxl_200_pdf.txt \
    > combined_pdf.txt
```

Choose either `xxs_pdf.txt` or `xxs_scatt_pdf.txt`, and choose the appropriate
one of `xxl_155_pdf.txt`, `xxl_175_pdf.txt`, or `xxl_200_pdf.txt`. The command
requires the rational weights to sum exactly to one and all PDFs to use the
same coordinate grid. Its weight, source-area, scaling, and final-area summary
is written to standard error, so redirecting standard output captures only the
combined two-column PDF.

## Piecewise-linear PDF compression

`pdf_tools/compress_pdf_linear.py` removes points that can be recovered by
linear interpolation within a relative error of `1e-6`:

```console
$ ./pdf_tools/compress_pdf_linear.py \
    six_figs_raw/xxs_pdf.txt > xxs_pdf_compressed.txt
```

It also accepts standard input, so a combined PDF can be compressed without an
intermediate uncompressed file:

```console
$ ./pdf_tools/weighted_average_pdfs.py WEIGHT PDF [WEIGHT PDF ...] |
    ./pdf_tools/compress_pdf_linear.py > combined_pdf_compressed.txt
```

Compression statistics are written to standard error. A different bound can
be selected with `--relative-error`, but the default is one millionth. For
zero-density input points, interpolation must recover exactly zero.

The compressed output represents piecewise-linear control points, not
left-aligned rectangular buckets. Convert it to a normalized three-column
`coordinate PDF CDF` table using trapezoidal integration:

```console
$ ./pdf_tools/build_cdf_from_convo_pdf.py \
    --linear-control-points combined_pdf_compressed.txt \
    > combined_pdf_cdf.txt
```

The lookup tool recognizes this three-column format, linearly interpolates the
PDF, and integrates it to obtain the quadratic CDF within each variable-width
segment.

## CDF p-value lookup

By default, `pdf_tools/build_cdf_from_convo_pdf.py` converts the weight
convolution's raw two-column, left-edge-aligned PDF into normalized CDF and
survival columns using rectangular bucket areas:

```console
$ ./pdf_tools/build_cdf_from_convo_pdf.py test.txt > test_cdf.txt
```

It can also read the convolution directly from standard input:

```console
$ ./weight_convolution | ./pdf_tools/build_cdf_from_convo_pdf.py > test_cdf.txt
```

For a PDF row at `x[i]`, its bucket area is
`pdf[i] * (x[i+1] - x[i])`. The CDF at `x[i]` contains the normalized area of
all preceding buckets, so it is zero at the first coordinate and exactly one
at the final coordinate. The survival column is accumulated independently from
the right, avoiding subtraction from a near-one CDF. Both tails are emitted in
scientific notation using float64 precision. Use `--linear-control-points`
instead for compressed PDFs, whose areas are trapezoids rather than left-aligned
rectangles.

`pdf_tools/cdf_lookup.py` recognizes the marked CDF/survival format and uses
the explicit survival column for upper-tail lookups. It also reads legacy
two-column CDFs. For a three-column control-point PDF/CDF table, it instead
integrates the interpolated PDF within each segment.

```console
$ python3 pdf_tools/cdf_lookup.py \
    test_cdf.txt 0.000015 \
    --show-density
1.5e-05  6.932971935e-06  0.462246577
```

The lookup output columns are the input value and p-value, followed by density
when `--show-density` is used. Pass `--upper-tail` to return `1 - CDF` (or, more
precisely, the table's total probability minus the CDF). Multiple lookup values
may be supplied in one invocation.

## Polynomial CDF compression

`pdf_tools/compress_cdf_poly.py` uses NumPy to compress an uncompressed,
equally spaced CDF/survival table into monotone, endpoint-constrained
fifth-order polynomial segments:

```console
$ ./pdf_tools/compress_cdf_poly.py out.txt > distribution.cdfpoly
```

Each output row contains:

```text
kind  start_x  end_x  y0  y1  q0  q1  q2  q3
```

Within that segment, `t = (x - start_x) / (end_x - start_x)`, and the
endpoint-constrained fifth-order representation is:

```text
q(t)    = q0 + q1*t + q2*t^2 + q3*t^3
tail(x) = (1-t)*y0 + t*y1 + t*(1-t)*q(t)
```

Storing `y0` and `y1` directly avoids cancellation when adjacent tail values
differ by many orders of magnitude.

`kind` is `C` for a lower-tail CDF polynomial and `S` for an upper-tail
survival polynomial. The compressor fits whichever tail is smaller, preserving
both lower- and upper-tail relative accuracy without subtractive cancellation.
Pass `--cdf-relative-only` to emit only `C` polynomials. Compression results are
written to standard error.

The complete billionth-relative-error pipeline is:

```console
$ ./pdf_tools/build_cdf_from_convo_pdf.py six_figs_raw/combo_155.txt |
    ./pdf_tools/compress_cdf_poly.py --relative-error 1e-9 \
    > combo_155.cdfpoly
```

Use `pdf_tools/cdf_poly_lookup.py` to query the compressed table:

```console
$ ./pdf_tools/cdf_poly_lookup.py distribution.cdfpoly 0.1 0.5 0.75
$ ./pdf_tools/cdf_poly_lookup.py distribution.cdfpoly 0.75 --upper-tail
```
