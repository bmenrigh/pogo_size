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


	fmt.Printf("Random key: %s and iv: %s\n", hex.EncodeToString(key), hex.EncodeToString(iv))

	aes_cipher, err := aes.NewCipher(key)

	if err != nil {
		fmt.Fprintln(os.Stderr, fmt.Sprintf("Unable to create AES cipher: %s", err.Error()))
		os.Exit(-1)
	}

	aes_ctr = cipher.NewCTR(aes_cipher, iv)

	enc := make([]byte, 8)
	null = make([]byte, 8)
	aes_ctr.XORKeyStream(enc, null)

	fmt.Printf("Random value: %s\n", hex.EncodeToString(enc))

	source := &Source{}
	rand := mathr.New(source)

	get_weights(rand)
}


func get_variate(rand *mathr.Rand) float64 {
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


func get_weights(rand *mathr.Rand) {

	weights := make(map[string]int64)

	for i := 0; i < 10000000; i++ {
		hv := get_variate(rand)
		hvsq := math.Pow(hv, 2.0)

		var wv float64
		wv = -10.0 // just has to be low enough to make hvsq = 1.5^2 still less than zero
		for (wv + hvsq) - 1.0 <= 0.0 {
			wv = get_variate(rand)
		}

		//fmt.Printf("0_0 %.07f %.07f %.07f\n", (wv + hvsq) - 1.0, hv, wv)


		w := fmt.Sprintf("%.04f", (wv + hvsq) - 1.0)
		_, ok := weights[w]
		if !ok {
		 	weights[w] = 0
		}

		weights[w]++
	}

	for k, v := range weights {
		fmt.Printf("%s %d\n", k, v)
	}
}
