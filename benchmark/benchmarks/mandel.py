# setup: import numpy as np; image = np.zeros((64, 32), dtype = np.uint8)
# run: mandel(-2.0, 1.0, -1.0, 1.0, image, 20)

# pythran export mandel(float, float, float, float, uint8[][], int)


def kernel(x, y, max_iters):
    """
      Given the real and imaginary parts of a complex number,
      determine if it is a candidate for membership in the Mandelbrot
      set given a fixed number of iterations.
    """
    c = complex(x, y)
    z = 0.0j
    for i in range(max_iters):
        z = z * z + c
        if (z.real * z.real + z.imag * z.imag) >= 4:
            return i

    return max_iters


def mandel(min_x, max_x, min_y, max_y, image, iters):
    height = image.shape[0]
    width = image.shape[1]

    pixel_size_x = (max_x - min_x) / width
    pixel_size_y = (max_y - min_y) / height

    for x in range(width):
        real = min_x + x * pixel_size_x
        for y in range(height):
            imag = min_y + y * pixel_size_y
            color = kernel(real, imag, iters)
            image[y, x] = color
