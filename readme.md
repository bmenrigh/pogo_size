[Showcase scores](https://twitter.com/bmenrigh_pogo/status/1680851346768150528?s=20)

[New Size System](https://twitter.com/bmenrigh_pogo/status/1618456354712350720?s=20)

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
kind  start_x  end_x  c0  c1  c2  c3  c4  c5
```

Within that segment, `t = (x - start_x) / (end_x - start_x)` and:

```text
tail(x) = c0 + c1*t + c2*t^2 + c3*t^3 + c4*t^4 + c5*t^5
```

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
