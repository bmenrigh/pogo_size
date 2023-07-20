package main

import (
	cryptor "crypto/rand"
	"os"
	"crypto/aes"
	"crypto/cipher"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	mathr "math/rand"
	math "math"
)

var max_h = 1.75 // The maximum height class one of {1.55, 1.75, 2.00}
var xxl_w = max_h - 1.5 // width of xxl class
var max_w = (max_h - 1.0) + 1.5 // Yes this is the same thing as + 0.5

var min_h = 0.49    // Scatterbug min is 0.25, all others min is 0.49
var xxs_w = 0.5 - min_h

var min_iv = 0 // To handle things like weather boost
var bucket_figs = 1 // the number of decimal digits for each bucket

var aes_ctr cipher.Stream
var null []byte

type reader struct{}

func (r *reader) Read(p []byte) (n int, err error) {
	//return cryptor.Read(p)
	aes_ctr.XORKeyStream(p, null)
	return len(p), nil
}

type Source struct{}

func (s *Source) Int63() (random int64) { // the lack of a returned error in the Source methods is unfortunate
	err := binary.Read(&reader{}, binary.BigEndian, &random)
	if err != nil {
		panic(fmt.Sprintf("converting random bytes to an int64: %s", err.Error()))
	}

	random &= 0x7FFFFFFFFFFFFFFF // Int63

	return random
}

func (s *Source) Seed(seed int64) {
	panic("you cannot seed the cryptographic source")
}

func main() {

	key := make([]byte, 16)
	n, err := cryptor.Read(key)

	if err != nil {
		fmt.Fprintln(os.Stderr, fmt.Sprintf("Unable to get random key: %s", err.Error()))
		os.Exit(-1)
	}

	if n != 16 {
		fmt.Fprintln(os.Stderr, fmt.Sprintf("Unable to get 16 random bytes for key, got: %d", n))
		os.Exit(-1)
	}

	iv := make([]byte, 16)
	n, err = cryptor.Read(iv)

	if err != nil {
		fmt.Fprintln(os.Stderr, fmt.Sprintf("Unable to get random iv: %s", err.Error()))
		os.Exit(-1)
	}

	if n != 16 {
		fmt.Fprintln(os.Stderr, fmt.Sprintf("Unable to get 16 random bytes for iv, got: %d", n))
		os.Exit(-1)
	}


	fmt.Fprintf(os.Stderr, "Random key: %s and iv: %s\n", hex.EncodeToString(key), hex.EncodeToString(iv))

	aes_cipher, err := aes.NewCipher(key)

	if err != nil {
		fmt.Fprintln(os.Stderr, fmt.Sprintf("Unable to create AES cipher: %s", err.Error()))
		os.Exit(-1)
	}

	aes_ctr = cipher.NewCTR(aes_cipher, iv)

	enc := make([]byte, 8)
	null = make([]byte, 8)
	aes_ctr.XORKeyStream(enc, null)

	fmt.Fprintf(os.Stderr, "Random value: %s\n", hex.EncodeToString(enc))
	//fmt.Fprintf(os.Stderr, "%.04f\n", 0.0001)
	//fmt.Fprintf(os.Stderr, "%.04f\n", 0.00005)
	//fmt.Fprintf(os.Stderr, "%.04f\n", 0.0000499)
	//fmt.Fprintf(os.Stderr, "%.04f\n", -0.0000499)
	//fmt.Fprintf(os.Stderr, "%.04f\n", -0.00005)
	//fmt.Fprintf(os.Stderr, "%.04f\n", -0.0001)

	source := &Source{}
	rand := mathr.New(source)

	get_weights(rand)
}


func get_weight_variate(rand *mathr.Rand) float64 {
	v := rand.NormFloat64()
	v = ((v / 8.0) + 1.0)

	if v < 0.5 {
		v = 0.5
	}

	if v > 1.5 {
		v = 1.5
	}

	return v
}


func get_size(rand *mathr.Rand) int {

	r := rand.Intn(1000)
	var s int
	switch {
	case r >= 0 && r < 4:
		s = 1
	case r >= 4 && r < 8:
		s = 5
	case r >= 8 && r < 33:
		s = 2
	case r >= 33 && r < 58:
		s = 4
	case r >= 58:
		s = 3
	}

	return s
}



func get_height_variate(rand *mathr.Rand, s int) float64 {
	v := rand.Float64()

	switch s {
	case 1:
		switch l := rand.Intn(20); l {
		case 0:
			return (v * (xxs_w * 0.2)) + min_h // s1 l
		default:
			return (v * (xxs_w * 0.8)) + (min_h + (xxs_w * 0.2)) // s1 u
		}
	case 2:
		return (v * 0.25) + 0.50; // s2
	case 3:
		return (v * 0.50) + 0.75; // s3
	case 4:
		return (v * 0.25) + 1.25; // s4
	case 5:
		switch l := rand.Intn(20); l {
		case 0:
			return (v * (xxl_w * 0.2)) + (1.5 + (xxl_w * 0.8)) // s5 l
		default:
			return (v * (xxl_w * 0.8)) + 1.5 // s5 u
		}
	default:
		os.Exit(-1)
	}


	//v = (v * 0.25) + 0.50; // Size class 2
	//v = (v * 0.5) + 0.75; // Size class 3

	//v = (v * 0.04) + 1.5; // s5 1.55 u
	//v = (v * 0.01) + 1.54; // s5 1.55 l
	//v = (v * 0.20) + 1.50; // s5 1.75 u
	//v = (v * 0.05) + 1.70; // s5 1.75 l
	//v = (v * 0.40) + 1.50; // s5 2.0 u
	//v = (v * 0.10) + 1.90; // s5 2.0 l

	//return v
	return -1.0
}


func score(h float64, w float64, iv int) float64 {
	// iv is the iv sum in the range [0, 45]

	return (h / max_h) * 800.0 + (float64(iv) / 45.0) * 50.0 + (w / max_w) * 150.0
}


func get_weights(rand *mathr.Rand) {

	scores := make(map[string]int64)


	b_factor := math.Pow10(bucket_figs)
	b_shift := 1.0 / (b_factor * 2.0)
	b_fmt := fmt.Sprintf("%%.0%df", bucket_figs)
	fmt.Fprintf(os.Stderr, "Buckets shifted by half a width (%.09f) to align bucket value to leftmost side of bucket\n", b_shift)

	iv_count := [46]int64{}
	for iv1 := min_iv; iv1 <= 15; iv1++ {
		for iv2 := min_iv; iv2 <= 15; iv2++ {
			for iv3 := min_iv; iv3 <= 15; iv3++ {
				iv_count[iv1 + iv2 + iv3]++
			}
		}
	}

	iter := int(math.Pow10(7))

	for i := 0; i < iter; i++ {
		//s := get_size(rand)
		s := 4

		hv := get_height_variate(rand, s)
		h := hv

		if (s < 5) {
			hv = hv * hv // square it
		}

		wv := get_weight_variate(rand)
		if (wv + hv) - 1.0 <= 0.0 {
			wv = 1.0
		}
		//fmt.Printf("0_0 %.07f %.07f %.07f\n", (wv + hvsq) - 1.0, hv, wv)

		w := (wv + hv) - 1.0

		for ivs, ivc := range iv_count {
			sc := score(h, w, ivs)

			//if sc > 1000 {
			//	fmt.Printf("Got score of %.4f for h %.4f, w %.4f, iv %d\n", sc, h, w, ivs)
			//}

			sc_str := fmt.Sprintf(b_fmt, sc - b_shift)

			//w := fmt.Sprintf(b_fmt, ((wv + hv) - 1.0) - b_shift)
			_, ok := scores[sc_str]
			if !ok {
				scores[sc_str] = 0
			}

			scores[sc_str] += ivc // The number of different ways this iv sum can be reached
		}
	}

	for k, v := range scores {
		fmt.Printf("%s %d\n", k, v)
	}
}
