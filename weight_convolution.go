package main

import (
	math "math"
)

var max_h = 1.75 // The maximum height class one of {1.55, 1.75, 2.00}
var xxl_w = max_h - 1.5 // width of xxl class
var max_w = (max_h - 1.0) + 1.5 // Yes this is the same thing as + 0.5

var min_h = 0.49    // Scatterbug min is 0.25, all others min is 0.49
var xxs_w = 0.5 - min_h

//                        min_h, xxs_l               xxs_u  xs    avg   xl  xxl_l                 xxl_u
var h_bounds = [8]float64{min_h, 0.5 - (0.8 * xxs_w), 0.5, 0.75, 1.25, 1.5, 1.5 +  (0.8 * xxl_w), max_h}
var h_area = [8]float64{0.0, 1.0 / (20.0 * 250.0), 19.0 / (20.0 * 250.0), 1.0 / 40.0, 471.0 / 500.0, 1.0 / 40.0, 19.0 / (20.0 * 250.0), 1.0 / (20.0 * 250.0)}

var bucket_figs = 3 // the number of decimal digits for each bucket
var bucket_w = 1.0 / math.Pow10(bucket_figs)


func main() {

}


func height_cdf(x float64) float64 {

	if x <= h_bounds[0] {
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

	if xp1 > 1.5 {
		p += height_cdf(xp1 + bucket_w) - height_cdf(xp1)
	}

	return p
}
