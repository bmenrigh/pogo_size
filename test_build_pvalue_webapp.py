import base64
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from build_pvalue_webapp import (
    PokemonRow,
    build_html,
    compact_display_extrema,
    compact_stats,
    pack_cdf,
    read_stats,
)
from pdf_tools.cdf_poly_lookup import PolynomialCDF


ROOT = Path(__file__).parent


class BuildPvalueWebappTests(unittest.TestCase):
    def test_cdf_segments_are_packed_losslessly(self):
        contents = (
            "# cdf-poly-v3 degree=5 basis=endpoint-q\n"
            "C 0 1 0 .5 .1 .2 .3 .4\n"
            "S 1 2 .5 0 -.1 -.2 -.3 -.4\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "cdf.txt")
            path.write_text(contents, encoding="utf-8")

            encoded, count = pack_cdf(path)

        unpacked = base64.b64decode(encoded)
        self.assertEqual(count, 2)
        self.assertEqual(len(unpacked), 2 * 65)
        self.assertEqual(struct.unpack_from("<B8d", unpacked), (0, 0, 1, 0, .5, .1, .2, .3, .4))
        self.assertEqual(struct.unpack_from("<B8d", unpacked, 65), (1, 1, 2, .5, 0, -.1, -.2, -.3, -.4))

    def test_stats_use_columnar_class_encoding(self):
        rows = [
            PokemonRow(1, "BULBASAUR", .7, 6.9, .49, 1.75),
            PokemonRow(664, "SCATTERBUG_ALL", .3, 2.5, .25, 1.75),
        ]

        names_json, columns_json = compact_stats(rows)
        names = json.loads(names_json).split("\n")
        columns = json.loads(columns_json)

        self.assertEqual(names, ["BULBASAUR", "SCATTERBUG_ALL"])
        self.assertEqual(columns[5], "01")
        self.assertEqual(columns[6], "11")

    def test_display_extrema_are_compactly_keyed_to_stats_rows(self):
        stats_path = ROOT / "pokemon_stats.tsv"
        rows = read_stats(stats_path)
        extrema = json.loads(compact_display_extrema(stats_path, rows))
        kyogre_index = next(
            index for index, row in enumerate(rows) if row.name == "KYOGRE"
        )
        kyogre = [entry for entry in extrema if entry[0] == kyogre_index]

        self.assertEqual(len(extrema), 230)
        self.assertIn(
            [
                kyogre_index,
                1,
                "6.975",
                "6.974999904632568359375",
                "6.98",
                "6.97",
            ],
            kyogre,
        )

    def test_real_build_is_standalone_and_fills_all_markers(self):
        html, pokemon_count, segment_count = build_html(
            ROOT / "pokemon_stats.tsv",
            ROOT / "cdfs_poly",
            ROOT / "pvalue_webapp_template.html",
            build_date=date(2026, 7, 22),
        )

        self.assertEqual(pokemon_count, 1115)
        self.assertEqual(segment_count, 837)
        self.assertNotIn("@@POKEMON", html)
        self.assertNotIn("@@DISPLAY", html)
        self.assertNotIn("@@CDF", html)
        self.assertNotIn("@@", html)
        self.assertIn('<time datetime="2026-07-22">July 22, 2026</time>', html)
        self.assertIn("© 2026 Pokémon. © 1995–2026 Nintendo", html)
        self.assertIn('class="site-footer"', html)
        self.assertIn("text-align: left; font-size: .64rem", html)
        self.assertIn("developed and operated by Scopely Explore", html)
        self.assertIn("good-faith claim of fair use", html)
        self.assertIn("This unofficial fan tool is not affiliated", html)
        self.assertIn("No ownership of the referenced Pokémon or Pokémon GO", html)
        self.assertNotIn("<script src=", html)
        self.assertNotIn("<link ", html)
        self.assertIn("<title>Pokémon Size Probability in Pokémon GO</title>", html)
        self.assertIn("<h1>Pokémon Size Probability in Pokémon GO</h1>", html)
        self.assertIn('<div class="eyebrow">Size prevalence lookup</div>', html)
        self.assertIn('id="height-value"', html)
        self.assertIn('id="weight-value"', html)
        self.assertIn('id="clear-pokemon"', html)
        self.assertIn('id="clear-height"', html)
        self.assertIn('id="clear-weight"', html)
        self.assertIn('aria-label="Clear selected Pokémon"', html)
        self.assertIn('aria-label="Clear observed height"', html)
        self.assertIn('aria-label="Clear observed weight"', html)
        self.assertIn('id="clear-pokemon" type="button" tabindex="-1"', html)
        self.assertIn('id="clear-weight" type="button" tabindex="-1"', html)
        self.assertIn('id="clear-height" type="button" tabindex="-1"', html)
        self.assertIn(
            'name="weight-interpretation" value="displayed" tabindex="-1"', html
        )
        self.assertIn(
            'name="height-interpretation" value="displayed" tabindex="-1"', html
        )
        self.assertIn("updateClearButton(measurement)", html)
        self.assertLess(html.index('id="weight-value"'), html.index('id="height-value"'))
        self.assertIn('name="height-interpretation"', html)
        self.assertIn('name="weight-interpretation"', html)
        self.assertNotIn('name="measurement"', html)
        self.assertIn("Weight and height tail probabilities", html)
        self.assertIn("Implied generation variates", html)
        self.assertIn('class="normalized-stack"', html)
        self.assertIn('analysis.displayed?"lookup ":""', html)
        self.assertIn("Enter a height, a weight, or both", html)
        self.assertIn('id="theme-switch"', html)
        self.assertIn('aria-label="Switch to dark theme"', html)
        self.assertIn('html[data-theme="dark"]', html)
        self.assertIn('localStorage.setItem("pogo-size-theme",theme)', html)
        self.assertIn("initThemeSwitch();initApp()", html)
        self.assertIn('input.addEventListener("focus",()=>input.select())', html)
        self.assertEqual(html.count('<details class="panel info-panel">'), 2)
        self.assertNotIn('<details class="panel info-panel" open', html)
        self.assertIn("1/250", html)
        self.assertIn("1/40", html)
        self.assertIn("471/500", html)
        self.assertIn("Is this a traditional statistical p-value?", html)
        self.assertIn("one-sided tail probability", html)
        self.assertIn("Does everyone who catches the same Pokémon", html)
        self.assertIn("its size class and intrinsic-weight variate", html)
        self.assertIn("intrinsic-weight variate <i>w</i><sub>v</sub> are shared", html)
        self.assertIn("strongly positively correlated between Trainers", html)
        self.assertIn("when catching Rattata or Magikarp", html)
        self.assertIn("10.17 kg and 0.41 m", html)
        self.assertIn("16.99 kg and 0.50 m", html)
        self.assertIn("[0.81, 0.83)", html)
        self.assertIn("0.81935–0.85265", html)
        self.assertIn("around the introduction of PokéStop Showcases", html)
        self.assertIn("exact transition date is not known", html)
        self.assertIn("Does evolution reroll a Pokémon’s height or weight?", html)
        self.assertIn("new height = old height × (new mean height / old mean height)", html)
        self.assertIn("different 1.55, 1.75, or 2.00 XXL height classes", html)
        self.assertIn("The intrinsic-weight variate remains unchanged", html)
        self.assertIn(
            "<b>Evolution between different XXL height classes</b> section "
            "in Technical Details",
            html,
        )
        self.assertIn("This is deterministic, not a reroll", html)
        self.assertIn("display rounding, not new randomness during evolution", html)
        self.assertIn("Evolution between different XXL height classes", html)
        self.assertIn("H<sub>t</sub> = 1.5μ<sub>t</sub>", html)
        self.assertIn("An XXL Skorupi measuring 1.22 m", html)
        self.assertIn("H<sub>t</sub> = 1.95 + 0.1(2.015 − 1.95) = 1.9565 m", html)
        self.assertIn("normalized height changes from 1.525 to 1.505", html)
        self.assertIn("A measured Noibat evolution provides a useful check", html)
        self.assertIn("between 115.55 and 117.01 kg", html)
        self.assertIn("observed Noivern was 2.29 m and 115.93 kg", html)
        self.assertIn(
            "confirm that <i>w</i><sub>v</sub> is preserved rather than rerolled",
            html,
        )
        self.assertNotIn(
            "rounded measurements cannot prove exact preservation", html
        )
        self.assertIn("Does trading reroll a Pokémon’s height or weight?", html)
        self.assertIn("Trading preserves the Pokémon’s existing height and weight", html)
        self.assertIn("trades formerly rerolled the intrinsic-weight variate", html)
        self.assertIn("date when trading changed", html)
        self.assertIn("Do conditional results show which class is most likely?", html)
        self.assertIn("does not perform that reverse inference", html)
        self.assertIn("Why can more than one conditional height class appear?", html)
        self.assertIn("How does Displayed mode affect Lower and Upper results?", html)
        self.assertIn("Where do the species data come from?", html)
        self.assertIn(
            "Does this calculator apply to Pokémon caught before XXS and XXL?", html
        )
        self.assertIn("December 8, 2022", html)
        self.assertIn("January 17, 2023", html)
        self.assertIn("data and knowledge are up to date as of that build date", html)
        self.assertIn("does not dynamically load new Game Master data", html)
        self.assertIn("Pokémon or forms released after the build date", html)
        self.assertIn("Why did I (bmenrigh) undertake this research?", html)
        self.assertIn("Measuring Up Pokémon", html)
        self.assertIn("u/TheParadoxMuse", html)
        self.assertIn("intermediate weight = w + (h² − 1)", html)
        self.assertIn("2.40625 kg", html)
        self.assertIn("1 in 8 Rattata", html)
        self.assertIn("13.125 kg", html)
        self.assertIn("Why is Zorua missing?", html)
        self.assertIn("Zorua has multiple in-game bugs", html)
        self.assertIn("Pumpkaboo and Gourgeist", html)
        self.assertIn("What other Pokémon are excluded?", html)
        self.assertIn("Hisuian Lilligant:", html)
        self.assertIn("Hisuian Avalugg:", html)
        self.assertIn("Black Kyurem:", html)
        self.assertIn("White Kyurem:", html)
        self.assertIn("likely a Game Master oversight or in-game data bug", html)
        self.assertIn("1.55, 1.75, and 2.00", html)
        self.assertIn("not known what criteria were used", html)
        self.assertIn("Eevee uses the 1.75 class", html)
        self.assertIn("Vaporeon uses the 1.55 class", html)
        self.assertIn("Scatterbug, Spewpa, and Vivillon", html)
        self.assertIn("Why can XL Pokémon be heavier than XXL Pokémon?", html)
        self.assertIn("hundreds of billions", html)
        self.assertIn("deterministic numerical convolution", html)
        self.assertIn("Why height needs no polynomial compression", html)
        self.assertIn("exact piecewise-linear CDF", html)
        self.assertIn("apply only to weight", html)
        self.assertIn("P(t) = (1 − t)y₀ + ty₁ + t(1 − t)Q(t)", html)
        self.assertIn("exponential search and then binary search", html)
        self.assertIn("Why both CDF and survival polynomials are stored", html)
        self.assertLess(
            html.index(
                "<h3>Why both CDF and survival polynomials are stored</h3>"
            ),
            html.index("<h3>Why height needs no polynomial compression</h3>"),
        )
        self.assertLess(
            html.index("<h3>Why height needs no polynomial compression</h3>"),
            html.index("<h3>How this page performs a lookup</h3>"),
        )
        self.assertIn("PDF density versus CDF probability", html)
        self.assertIn("piecewise smooth, not globally differentiable", html)
        self.assertIn("non-smooth breakpoint", html)
        self.assertIn("its CDF is continuous", html)
        self.assertIn("exhaustive point-by-point validation", html)
        self.assertIn("captured either by a polynomial boundary", html)
        self.assertIn("Accuracy and model limitations", html)
        self.assertIn("Every practical care has been taken", html)
        self.assertIn("polynomial-compression error", html)
        self.assertIn("no separate formal", html)
        self.assertIn("Overall population</b> result additionally assumes", html)
        self.assertIn("only the per-class conditional probability is meaningful", html)
        self.assertIn("does not depend on how frequently the different classes occur", html)
        self.assertIn("do not quantize every generated outcome", html)
        self.assertIn("fewer than one billion distinct float32 values", html)
        self.assertIn("as accurate as practically achievable", html)
        self.assertIn("prevent perfect accuracy", html)
        self.assertIn("embeds 837 polynomial segments across 12 distributions", html)
        self.assertIn("that large PDF is not included in this page", html)
        self.assertIn("answers tail-probability questions", html)
        self.assertIn('href="https://github.com/bmenrigh/pogo_size"', html)
        self.assertIn("needed to reproduce this application", html)
        self.assertIn("How the game generates height and weight", html)
        self.assertIn("chooses the size class first", html)
        self.assertIn("exact random-selection implementation is not known", html)
        self.assertNotIn("an integer from 0 through 999", html)
        self.assertIn("intrinsic-weight variate <i>w</i><sub>v</sub>", html)
        self.assertNotIn("intrinsic-weight variate <i>i</i>", html)
        self.assertIn("The XXS and XXL height-density steps", html)
        self.assertIn("an upward jump by a factor of 4.75", html)
        self.assertIn("replaces the <b>intrinsic-weight variate</b>", html)
        self.assertIn("½ erfc(2√2)", html)
        self.assertIn("0.003167124183311996%", html)
        self.assertLess(
            html.index("How the game generates height and weight"),
            html.index("Exact probability at the weight clamps"),
        )
        self.assertLess(
            html.index("Exact probability at the weight clamps"),
            html.index("The XXS and XXL height-density steps"),
        )
        self.assertLess(
            html.index("The XXS and XXL height-density steps"),
            html.index("<h3>Evolution between different XXL height classes</h3>"),
        )
        self.assertIn("Can float32 change", html)
        self.assertIn("This behavior is theorized, not verified in practice", html)
        self.assertIn("no real-world example has come forward", html)
        self.assertIn("Can a Pokémon display a weight of 0 kg?", html)
        self.assertIn("both the XXS and XS size classes", html)
        self.assertIn("1 in 50.6 million", html)
        self.assertIn("Does the Pokédex use the same rounding", html)
        self.assertIn("models the rounded height or weight shown for an individual Pokémon only", html)
        self.assertEqual(html.count('class="heavy-ball-side"'), 2)
        self.assertEqual(html.count('class="heavy-ball-dot"'), 2)
        self.assertEqual(html.count('class="heavy-ball-upper-shell"'), 1)
        self.assertEqual(html.count('class="heavy-ball-lower-shell"'), 1)
        self.assertEqual(html.count('class="heavy-ball-band"'), 1)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required")
    def test_javascript_polynomial_lookup_matches_python(self):
        html, _, _ = build_html(
            ROOT / "pokemon_stats.tsv",
            ROOT / "cdfs_poly",
            ROOT / "pvalue_webapp_template.html",
        )
        script = html.rsplit("<script>", 1)[1].split("</script>", 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory, "app.js")
            module.write_text(script, encoding="utf-8")
            command = (
                "const a=require(process.argv[1]);"
                "const p=a.POKEMON.find(p=>p.name==='BULBASAUR_ALL');"
                "const b=a.POKEMON.find(p=>p.name==='BIDOOF');"
                "const k=a.POKEMON.find(p=>p.name==='KYOGRE');"
                "const resultNode={innerHTML:''};"
                "global.document={getElementById:()=>resultNode};"
                "a.renderResults(p,{height:{rawValue:'0.700',observed:.7,displayed:false}},false);"
                "const heightOnly=resultNode.innerHTML;"
                "a.renderResults(p,{weight:{rawValue:'6.900',observed:6.9,displayed:false}},false);"
                "const weightOnly=resultNode.innerHTML;"
                "a.renderResults(p,{},false);"
                "const neither=resultNode.innerHTML;"
                "a.renderResults(p,{"
                "height:{rawValue:'0.700',observed:.7,displayed:false},"
                "weight:{rawValue:'6.900',observed:6.9,displayed:false}},false);"
                "const both=resultNode.innerHTML;"
                "console.log(JSON.stringify({"
                "tails:a.polynomialTails('full175',1.234567),"
                "classes:[.49,.5,.75,1.25,1.5,1.75].map(x=>a.heightClass(x,p)),"
                "supports:['xxs','xs','average','xl','xxl'].map(c=>a.weightSupport(p,c)),"
                "places:['2','2.4','2.41','2.410','2.41e0'].map(a.decimalPlaces),"
                "displayedLower:a.interpretedObservation('2.41',2.41,true,false,'kg'),"
                "displayedUpper:a.interpretedObservation('2.41',2.41,true,true,'kg'),"
                "displayedZero:a.interpretedObservation('0',0,true,true,'kg'),"
                "profile:a.pokemonProfile(p),"
                "extremaCount:a.DISPLAY_EXTREMA.length,"
                "kyogreNote:a.displayExtremaNotes(k),"
                "straddles:['xxs','xs','average','xl','xxl'].filter(c=>"
                "a.rangeIntersects(.345/.7,.355/.7,a.heightClassSupport(p,c))),"
                "oneIn:a.oneInText(.001,'weight',5,false,'kg'),"
                "conditional:a.oneInText(a.heightTails(.4/p.height,p,'xs')[0],"
                "'height',.4,false,'m','XS Pokémon'),"
                "exactVariates:a.impliedVariates(p,"
                "a.analyzeMeasurement('height','0.700',.7,p,false,false),"
                "a.analyzeMeasurement('weight','8.280',8.28,p,false,false)),"
                "xxlVariates:a.impliedVariates(p,"
                "a.analyzeMeasurement('height','1.120',1.12,p,false,false),"
                "a.analyzeMeasurement('weight','7.590',7.59,p,false,false)),"
                "displayedVariates:a.impliedVariates(p,"
                "a.analyzeMeasurement('height','0.70',.7,p,false,true),"
                "a.analyzeMeasurement('weight','6.90',6.9,p,false,true)),"
                "bidoofOne:a.impliedVariates(b,"
                "a.analyzeMeasurement('height','0.41',.41,b,false,true),"
                "a.analyzeMeasurement('weight','10.17',10.17,b,false,true)),"
                "bidoofTwo:a.impliedVariates(b,"
                "a.analyzeMeasurement('height','0.50',.5,b,false,true),"
                "a.analyzeMeasurement('weight','16.99',16.99,b,false,true)),"
                "singleRangeHtml:a.renderVariates(p,"
                "a.analyzeMeasurement('height','0.70',.7,p,false,true),"
                "a.analyzeMeasurement('weight','6.90',6.9,p,false,true)),"
                "crossesXXL:a.transformedHeightRange(1.492857142857,1.507142857143,p),"
                "crossesXXLRanges:a.transformedHeightRanges(1.492857142857,1.507142857143,p),"
                "crossingVariates:a.impliedVariates(p,"
                "a.analyzeMeasurement('height','1.05',1.05,p,false,true),"
                "a.analyzeMeasurement('weight','12.42',12.42,p,false,true)),"
                "crossingHtml:a.renderVariates(p,"
                "a.analyzeMeasurement('height','1.05',1.05,p,false,true),"
                "a.analyzeMeasurement('weight','12.42',12.42,p,false,true)),"
                "heightOnly,heightOnlyHasWeight:heightOnly.includes('Weight probabilities'),"
                "weightOnly,weightOnlyHasHeight:weightOnly.includes('Height probabilities'),"
                "neither,both"
                "}))"
            )
            result = json.loads(
                subprocess.check_output(
                    ["node", "-e", command, str(module)], text=True
                )
            )

        expected = PolynomialCDF.from_path(
            ROOT / "cdfs_poly" / "full_175.txt"
        ).lookup_tails(1.234567)
        self.assertEqual(tuple(result["tails"]), expected)
        self.assertEqual(
            result["classes"],
            ["xxs", "xs", "average", "average", "xl", "xxl"],
        )
        self.assertEqual(
            result["supports"],
            [[0, 0.75], [0, 1.0625], [0.0625, 2.0625], [1.0625, 2.75], [1, 2.25]],
        )
        self.assertEqual(result["places"][:4], [0, 1, 2, 3])
        self.assertIsNone(result["places"][4])  # JSON encodes Infinity as null.
        self.assertEqual(result["displayedLower"]["lower"], 2.405)
        self.assertEqual(result["displayedLower"]["upper"], 2.415)
        self.assertEqual(result["displayedLower"]["lookup"], 2.4149999999999996)
        self.assertEqual(result["displayedUpper"]["lookup"], 2.405)
        self.assertEqual(result["displayedZero"]["lower"], 0)
        self.assertEqual(result["displayedZero"]["upper"], 0.005)
        self.assertIn(
            "using exact value 2.4149999999999996 kg (just below 2.415 kg)",
            result["displayedLower"]["note"],
        )
        self.assertIn(
            "using exact value 2.405 kg", result["displayedUpper"]["note"]
        )
        self.assertEqual(result["straddles"], ["xxs", "xs"])
        self.assertIn("Mean height", result["profile"])
        self.assertIn("Mean weight", result["profile"])
        self.assertLess(
            result["profile"].index("Mean weight"),
            result["profile"].index("Mean height"),
        )
        self.assertLess(
            result["profile"].index("Weight range"),
            result["profile"].index("Height range"),
        )
        self.assertIn("1.75× mean", result["profile"])
        self.assertIn("0.343–0.35 m", result["profile"])
        self.assertIn("7.33125–18.975 kg", result["profile"])
        self.assertIn("6.9–15.525 kg", result["profile"])
        self.assertNotIn("height²", result["profile"])
        self.assertEqual(result["extremaCount"], 230)
        self.assertIn("Maximum height:", result["kyogreNote"])
        self.assertIn("6.974999904632568359375", result["kyogreNote"])
        self.assertIn("display as 6.97 m", result["kyogreNote"])
        self.assertEqual(
            result["oneIn"],
            "About 1 in 1,000 Pokémon caught weigh less than or equal to 5 kg.",
        )
        self.assertEqual(
            result["conditional"],
            "About 1 in 3.5 XS Pokémon are shorter than or equal to 0.4 m.",
        )
        self.assertTrue(result["exactVariates"]["possible"])
        self.assertAlmostEqual(result["exactVariates"]["heightLower"], 1)
        self.assertAlmostEqual(result["exactVariates"]["weightLower"], 1.2)
        self.assertEqual(
            result["exactVariates"]["weightLower"],
            result["exactVariates"]["weightUpper"],
        )
        self.assertTrue(result["xxlVariates"]["possible"])
        self.assertAlmostEqual(result["xxlVariates"]["heightLower"], 1.6)
        self.assertAlmostEqual(result["xxlVariates"]["weightLower"], 0.5)
        self.assertLess(result["displayedVariates"]["heightLower"], 1)
        self.assertGreater(result["displayedVariates"]["heightUpper"], 1)
        self.assertLess(
            result["displayedVariates"]["weightLower"],
            result["displayedVariates"]["weightUpper"],
        )
        self.assertAlmostEqual(result["bidoofOne"]["heightLower"], 0.81)
        self.assertAlmostEqual(result["bidoofOne"]["heightUpper"], 0.83)
        self.assertAlmostEqual(result["bidoofOne"]["weightLower"], 0.81935)
        self.assertAlmostEqual(result["bidoofOne"]["weightUpper"], 0.85265)
        self.assertAlmostEqual(result["bidoofTwo"]["heightLower"], 0.99)
        self.assertAlmostEqual(result["bidoofTwo"]["heightUpper"], 1.01)
        self.assertAlmostEqual(result["bidoofTwo"]["weightLower"], 0.82915)
        self.assertAlmostEqual(result["bidoofTwo"]["weightUpper"], 0.86965)
        self.assertIn("Intrinsic-weight variate", result["singleRangeHtml"])
        self.assertNotIn("Average:", result["singleRangeHtml"])
        self.assertAlmostEqual(result["crossesXXL"][0], 1.5000000000000002)
        self.assertAlmostEqual(result["crossesXXL"][1], 2.25)
        self.assertEqual(len(result["crossesXXLRanges"]), 2)
        self.assertAlmostEqual(result["crossesXXLRanges"][0][1], 2.25)
        self.assertAlmostEqual(result["crossesXXLRanges"][1][0], 1.5)
        self.assertTrue(result["crossingVariates"]["possible"])
        self.assertEqual(len(result["crossingVariates"]["weightRanges"]), 2)
        self.assertEqual(
            result["crossingVariates"]["weightRangeClasses"], [["xl"], ["xxl"]]
        )
        self.assertGreater(result["crossingVariates"]["weightRanges"][0][0], 0.54)
        self.assertLess(result["crossingVariates"]["weightRanges"][0][1], 0.58)
        self.assertGreater(result["crossingVariates"]["weightRanges"][1][0], 1.29)
        self.assertLess(result["crossingVariates"]["weightRanges"][1][1], 1.31)
        self.assertIn("XL: 0.", result["crossingHtml"])
        self.assertIn("XXL: 1.", result["crossingHtml"])
        self.assertIn("Height probabilities", result["heightOnly"])
        self.assertFalse(result["heightOnlyHasWeight"])
        self.assertIn("Weight probabilities", result["weightOnly"])
        self.assertFalse(result["weightOnlyHasHeight"])
        self.assertNotIn("Matches height", result["weightOnly"])
        self.assertIn("Mean height", result["neither"])
        self.assertIn(
            "Enter a height, a weight, or both to calculate tail probabilities.",
            result["neither"],
        )
        self.assertLess(
            result["both"].index("Weight probabilities"),
            result["both"].index("Height probabilities"),
        )
        self.assertEqual(result["both"].count("Matches height"), 1)
        self.assertIn("class-row observed-class", result["both"])


if __name__ == "__main__":
    unittest.main()
