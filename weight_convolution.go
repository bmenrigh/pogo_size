package main

import (
	"math"
	"fmt"
)

var max_h = 1.75 // The maximum height class one of {1.55, 1.75, 2.00}
var xxl_w = max_h - 1.5 // width of xxl class

var min_h = 0.49    // Scatterbug min is 0.25, all others min is 0.49
var xxs_w = 0.5 - min_h

//                        min_h, xxs_l               xxs_u  xs    avg   xl  xxl_l                 xxl_u
var h_bounds = [8]float64{min_h, 0.5 - (0.8 * xxs_w), 0.5, 0.75, 1.25, 1.5, 1.5 +  (0.8 * xxl_w), max_h}
var h_area = [8]float64{0.0, 1.0 / (20.0 * 250.0), 19.0 / (20.0 * 250.0), 1.0 / 40.0, 471.0 / 500.0, 1.0 / 40.0, 19.0 / (20.0 * 250.0), 1.0 / (20.0 * 250.0)}

var bucket_figs = 4 // the number of decimal digits for each bucket
var bucket_inv = math.Pow10(bucket_figs)
var bucket_w = 1.0 / bucket_inv
var b_shift = bucket_w / 2.0
var b_fmt = fmt.Sprintf("%%.0%df", bucket_figs)

//var min_h2m1 = math.Round((math.Pow(min_h, 2.0) - 1.0) * bucket_inv) / bucket_inv
//var max_h2m1 = math.Round((math.Pow(1.5, 2.0) - 1.0) * bucket_inv) / bucket_inv

var min_h2m1 = math.Pow(min_h, 2.0) - 1.0
var max_h2m1 = math.Pow(1.5, 2.0) - 1.0

var erf_norm_factor = (1.0 / 8.0) * math.Sqrt(2.0) // normalization to error function for normal CDF
var pdf_norm_factor = (1.0 / 8.0) * math.Sqrt(2.0 * math.Pi) // normalization to normal PDF

var weight_buckets map[string]float64

var h_x_cache []float64
var h_p_cache []float64

var w_x_cache []float64
var w_p_cache []float64


func main() {
	weight_buckets = make(map[string]float64)
	h_x_cache = make([]float64, 0, int(math.Round((math.Pow(1.5, 2.0) - math.Pow(min_h, 2.0)) * bucket_inv) + 1))
	h_p_cache = make([]float64, 0, int(math.Round((math.Pow(1.5, 2.0) - math.Pow(min_h, 2.0)) * bucket_inv) + 1))

	w_x_cache = make([]float64, 0, int(((1.5 - 0.5) * bucket_inv) + 1))
	w_p_cache = make([]float64, 0, int(((1.5 - 0.5) * bucket_inv) + 1))

	// Experimentation shows incremeting by bucket_w when starting from
	// min_h2m1 which may not be exactly representable by a float64
	// results in a small amount of error accumulating over the whole loop
	// so instead incremeting by 1 and doing a division on each step
	// eliminates errors from accumulating
	for hx := min_h2m1 * bucket_inv; hx < max_h2m1 * bucket_inv - 0.5; hx += 1 {
		phx := height21m1_pdf(hx * bucket_w)

		phx_sum += phx

		h_x_cache = append(h_x_cache, hx * bucket_w)
		h_p_cache = append(h_p_cache, phx)
	}

	// Starting here at 0.5 which has an exact representation
	// has no accumulated error issues
	for wx := 0.5; wx < 1.5 - b_shift; wx += bucket_w {
		pwx := weight_pdf(wx)

		pwx_sum += pwx

		w_x_cache = append(w_x_cache, wx)
		w_p_cache = append(w_p_cache, pwx)
	}

	// The magic
	build_w_pdf()

	add_weight(0.0 - bucket_w, 0.0);
	add_weight(max_h2m1 + 1.5, 0.0);
	for k, v := range weight_buckets {
		fmt.Printf("%s\t%.015f\n", k, v)
	}
}


func build_w_pdf() {

	// Handle the weight pdf spikes at 0.5 and 1.5
	var pwp5 = weight_cdf(0.5) // This has the same probability as the spike at 1.5

	for i, hx := range h_x_cache {
		phx := h_p_cache[i]

		if hx + 0.5 < 0.0 - b_shift {
			add_weight(hx + 1.0, phx * pwp5)
		} else {
			add_weight(hx + 0.5, phx * pwp5)
		}

		add_weight(hx + 1.5, phx * pwp5)
	}

	// Now do the convolution between the weight normal dist and the the height21m1 dist
	for i, wx := range w_x_cache {
		pwx := w_p_cache[i]

		for j, hx := range h_x_cache {
			phx := h_p_cache[j]

			if hx + wx < 0.0 - (bucket_w + b_shift) {
				add_weight(hx + 1.0, phx * pwx)
			} else if hx + wx > 0.0 - (bucket_w + b_shift) && hx + wx < 0.0 - b_shift {
				// This straddles zero
				add_weight(hx + 1.0, (phx * pwx) / 2.0)
				add_weight(hx + wx + bucket_w, (phx * pwx) / 2.0)
			} else {
				add_weight(hx + wx, (phx * pwx) / 2.0)
				add_weight(hx + wx + bucket_w, (phx * pwx) / 2.0)
			}
		}
	}

}


func add_weight(w, p float64) {


	w_shift := w // no shift
	// Fix -0.0000
	if w_shift < 0.0 && w_shift > 0.0 - b_shift {
		w_shift = 0.0
	}

	wstr := fmt.Sprintf(b_fmt, w_shift)

	_, ok := weight_buckets[wstr]
	if !ok {
		weight_buckets[wstr] = 0.0
	}

	weight_buckets[wstr] += p
}


func height_cdf(x float64) float64 {

	if x < h_bounds[0] {
		return 0.0
	}

	if x >= h_bounds[7] {
		return 1.0
	}

	sum_p := 0.0 // The running CDF sum
	for i := 1; i < 8; i++ {
		if x > h_bounds[i] {
			sum_p += h_area[i]
		} else {
			sum_p += h_area[i] * ((x - h_bounds[i - 1]) / (h_bounds[i] - h_bounds[i - 1]))

			return sum_p
		}
	}

	return -1.0 // should be unreachable
}


func height21m1_pdf(x float64) float64 {

	// This is the height^2 - 1 combined wih height - 1 distributions

	// This function assumes x is left-aligned to bin

	// This function assumes the h^2 portion always covers the h^1
	// part of the distribution which is true unless the max height is
	// greater than 2.25 which isn't currently possible

	xp1 := x + 1 // undo -1 shift

	p := height_cdf(math.Sqrt(xp1 + bucket_w)) - height_cdf(math.Sqrt(xp1))

	if xp1 >= 1.5 {
		p += height_cdf(xp1 + bucket_w) - height_cdf(xp1)
	}

	return p
}


func weight_cdf(x float64) float64 {

	// Normal distribution CDF is 1/2 * (1 + erf((x - u) / (sigma * sqrt(2))))

	return 0.5 * (1.0 + math.Erf((x - 1.0) / erf_norm_factor)) * bucket_inv
}


func weight_pdf(x float64) float64 {

	return weight_cdf(x + bucket_w) - weight_cdf(x)
}
